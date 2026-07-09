"""Split-conformal calibration of exported intervals and probability curves.

The production models train on 2021-2024, so their intervals cannot be
honestly assessed on any of those seasons. This module fits a second copy
of each market's models on 2021-2023 ONLY, scores it on held-out 2024
(features are as-of by construction, so 2024 predictions are walk-forward),
and derives fixed per-market adjustments that are applied unchanged to
everything downstream: the 2025 backtest AND the demo-week export. The
production point/mean models stay trained on all of 2021-2024; only the
interval/curve calibration comes from the 2024 split.

Two methods, chosen by market type:

* Yardage markets (pass_yds, rush_yds, rec_yds) -- per-quantile additive
  conformal. delta_tau = finite-sample tau-quantile of the 2024 residuals
  (y - q_hat_tau(x)); adjusted quantiles are floored at 0 and re-sorted,
  and the probability curve is rebuilt through them, so probCurve /
  overProbAtRef soften consistently with the widened band.

* Count markets (receptions, pass_tds) -- the raw quantile models are
  degenerate in the lower tail (p05/p10 identically 0), which marginal
  conformal cannot fix because counts are zero-inflated. Instead the
  exported distribution becomes a negative-binomial (Poisson when the
  fitted dispersion alpha is 0) layer: lambda = mean-model expectation
  x a 2024-fit scale, dispersion fit on 2024 by likelihood grid, plus a
  mid-PIT conformal "level map" that reshapes the CDF so 2024 PIT values
  are uniform. Quantiles and P(over) curves are read off the
  continuity-corrected CDF on half-integer support, so low quantiles vary
  by player instead of collapsing to 0 and integer lines correctly
  exclude the push mass (P(over k) = P(Y >= k+1)).

Conformity scores are drawn from 2024 rows only -- never 2025. That is
enforced by ``calibration_mask`` and covered by tests/test_conformal.py.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from edgefinder.features import FEATURES, MARKETS
from edgefinder.train import (
    MODELS_DIR,
    MIN_PRIOR_PLAYED,
    QUANTILES,
    Q_INDEX,
    _hgb,
    yards_prob_curve,
)

CAL_SEASON = 2024
CAL_TRAIN_SEASONS = (2021, 2022, 2023)
COUNT_MARKETS = ("receptions", "pass_tds")

LAM_FLOOR = 0.05
ALPHA_GRID = (0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075,
              0.1, 0.15, 0.2, 0.3, 0.5)
#: PIT levels at which the count-market level map is anchored
LEVEL_GRID = np.round(np.concatenate([[0.02], np.arange(0.05, 0.951, 0.05),
                                      [0.98]]), 3)
MAX_COUNT = 40          # count-market support cap (receptions never near it)
CURVE_MIN_OVER = 0.02   # trim count curves once P(over) falls below this


def params_path(models_dir: Path = MODELS_DIR) -> Path:
    return models_dir / "conformal.json"


def calibration_train_mask(frame: pd.DataFrame) -> pd.Series:
    """Rows the CALIBRATION models may train on: 2021-2023 only."""
    return (
        frame["season"].isin(CAL_TRAIN_SEASONS)
        & frame["played"]
        & frame["eligible"]
        & (frame["prior_played"] >= MIN_PRIOR_PLAYED)
        & frame["y"].notna()
    )


def calibration_mask(frame: pd.DataFrame) -> pd.Series:
    """Rows conformity scores are computed on: held-out 2024 ONLY.

    2025 is the evaluation season and must never contribute a score.
    """
    return (
        (frame["season"] == CAL_SEASON)
        & frame["played"]
        & frame["eligible"]
        & (frame["prior_played"] >= MIN_PRIOR_PLAYED)
        & frame["y"].notna()
    )


def _fs_quantile(scores: np.ndarray, tau: float) -> float:
    """Finite-sample-corrected empirical quantile of conformity scores.

    Upper-tail levels use ceil((n+1)*tau)/n (conservative upward), lower
    tails floor((n+1)*tau)/n (conservative downward) -- the standard
    split-conformal order statistics.
    """
    s = np.sort(np.asarray(scores, dtype=float))
    n = len(s)
    if n == 0:
        raise ValueError("no conformity scores")
    if tau >= 0.5:
        k = min(n, math.ceil((n + 1) * tau))
    else:
        k = max(1, math.floor((n + 1) * tau))
    return float(s[k - 1])


def _nb_dist(lam, alpha: float):
    """NB2 with Var = lam + alpha*lam^2; Poisson when alpha == 0."""
    if alpha <= 1e-9:
        return stats.poisson(lam)
    r = 1.0 / alpha
    return stats.nbinom(r, r / (r + lam))


def _fit_yards(y: np.ndarray, qpred: np.ndarray) -> dict:
    """Per-quantile additive deltas from 2024 residuals."""
    return {
        "method": "additive",
        "deltas": {f"{q:.2f}": round(_fs_quantile(y - qpred[:, i], q), 4)
                   for q, i in Q_INDEX.items()},
    }


def _fit_count(y: np.ndarray, mean_pred: np.ndarray) -> dict:
    """Calibrated NB/Poisson layer: lambda scale + dispersion + level map."""
    lam0 = np.clip(mean_pred, LAM_FLOOR, None)
    lam_scale = float(np.mean(y) / np.mean(lam0))
    lam = lam0 * lam_scale

    best_alpha, best_ll = 0.0, -math.inf
    for a in ALPHA_GRID:
        ll = float(np.sum(_nb_dist(lam, a).logpmf(y)))
        if ll > best_ll:
            best_alpha, best_ll = a, ll

    dist = _nb_dist(lam, best_alpha)
    pit = dist.cdf(y - 1) + 0.5 * dist.pmf(y)  # mid-PIT for discrete y
    raw = np.array([_fs_quantile(pit, t) for t in LEVEL_GRID])
    raw = np.concatenate([[0.0], np.maximum.accumulate(raw), [1.0]])
    target = np.concatenate([[0.0], LEVEL_GRID, [1.0]])
    for i in range(1, len(raw)):  # strictify for invertible interpolation
        if raw[i] <= raw[i - 1]:
            raw[i] = raw[i - 1] + 1e-9
    return {
        "method": "count_nb",
        "lambdaScale": round(lam_scale, 4),
        "alpha": best_alpha,
        "levelMap": {"raw": [float(v) for v in raw],
                     "target": [float(v) for v in target]},
    }


def fit_conformal(
    frames: dict[str, pd.DataFrame],
    models: dict,
    models_dir: Path = MODELS_DIR,
) -> "Calibrator":
    """Fit 2021-2023 models, score 2024, persist + return the calibrator."""
    params: dict = {
        "calSeason": CAL_SEASON,
        "calTrainSeasons": list(CAL_TRAIN_SEASONS),
        "markets": {},
    }
    for market, frame in frames.items():
        depth = models[market].train_info.get("max_depth", 5)
        tr = frame[calibration_train_mask(frame)]
        cal = frame[calibration_mask(frame)]
        X, y_tr = tr[FEATURES], tr["y"].to_numpy()
        Xc, yc = cal[FEATURES], cal["y"].to_numpy()

        if market in COUNT_MARKETS:
            mean_model = _hgb("squared_error", depth).fit(X, y_tr)
            mp = _fit_count(yc, np.clip(mean_model.predict(Xc), 0.0, None))
            detail = (f"lam_scale={mp['lambdaScale']:.4f} "
                      f"alpha={mp['alpha']}")
        else:
            qpred = np.column_stack([
                _hgb("quantile", depth, quantile=q).fit(X, y_tr).predict(Xc)
                for q in QUANTILES
            ])
            qpred = np.sort(np.clip(qpred, 0.0, None), axis=1)
            mp = _fit_yards(yc, qpred)
            detail = (f"d10={mp['deltas']['0.10']:+.2f} "
                      f"d90={mp['deltas']['0.90']:+.2f}")
        mp["nCal"] = int(len(cal))
        params["markets"][market] = mp
        print(f"conformal {market}: n_cal={mp['nCal']} "
              f"method={mp['method']} {detail}")

    models_dir.mkdir(parents=True, exist_ok=True)
    params_path(models_dir).write_text(json.dumps(params, indent=2))
    return Calibrator(params)


def load_calibrator(models_dir: Path = MODELS_DIR) -> "Calibrator":
    return Calibrator(json.loads(params_path(models_dir).read_text()))


class Calibrator:
    """Applies the fixed 2024-fit adjustments to quantiles and curves."""

    def __init__(self, params: dict):
        self.meta = {k: v for k, v in params.items() if k != "markets"}
        self.markets: dict[str, dict] = params["markets"]

    # -- count-market internals -----------------------------------------

    @staticmethod
    def _lam(p: dict, mean_pred) -> np.ndarray:
        return np.clip(np.asarray(mean_pred, dtype=float),
                       LAM_FLOOR, None) * p["lambdaScale"]

    @staticmethod
    def _level(p: dict, cdf_val):
        """Raw CDF value -> calibrated level (the mid-PIT level map)."""
        lm = p["levelMap"]
        return np.interp(cdf_val, lm["raw"], lm["target"])

    @staticmethod
    def _inv_level(p: dict, target: float) -> float:
        lm = p["levelMap"]
        return float(np.interp(target, lm["target"], lm["raw"]))

    @staticmethod
    def _cc_quantiles(lam: float, alpha: float, levels) -> np.ndarray:
        """Continuity-corrected quantiles: CDF interp on half-integer support."""
        dist = _nb_dist(lam, alpha)
        ks = np.arange(0, MAX_COUNT + 1)
        xs = np.concatenate([[-0.5], ks + 0.5])
        cdf = np.concatenate([[0.0], dist.cdf(ks)])
        keep = np.concatenate([[True], np.diff(cdf) > 1e-12])
        return np.interp(levels, cdf[keep], xs[keep])

    # -- public API ------------------------------------------------------

    def quantile_matrix(
        self, market: str, raw_q: np.ndarray, mean_pred
    ) -> np.ndarray:
        """(n, 7) calibrated quantiles for export/eval (monotone, >= 0)."""
        p = self.markets[market]
        if p["method"] == "additive":
            deltas = np.array([p["deltas"][f"{q:.2f}"] for q in QUANTILES])
            adj = raw_q + deltas[None, :]
        else:
            lam = self._lam(p, mean_pred)
            levels = [self._inv_level(p, q) for q in QUANTILES]
            adj = np.empty((len(lam), len(QUANTILES)))
            for i, lam_i in enumerate(lam):
                adj[i] = self._cc_quantiles(lam_i, p["alpha"], levels)
        return np.sort(np.clip(adj, 0.0, None), axis=1)

    def prob_curve(self, market: str, qadj_row: np.ndarray,
                   mean_pred_i: float) -> list[dict]:
        """Calibrated P(over line) curve for one row."""
        p = self.markets[market]
        if p["method"] == "additive":
            return yards_prob_curve(qadj_row, MARKETS[market]["step"])
        lam = float(self._lam(p, mean_pred_i))
        if market == "pass_tds":
            return self._pass_tds_curve(lam, p)
        return self._count_curve(lam, p)

    def _survival(self, p: dict, dist, k: int) -> float:
        """Calibrated P(Y > k) = P(Y >= k+1)."""
        return float(1.0 - self._level(p, dist.cdf(k)))

    def _count_curve(self, lam: float, p: dict) -> list[dict]:
        """Step curve on the 0.5 grid: P(over k) == P(over k+0.5)."""
        dist = _nb_dist(lam, p["alpha"])
        lines = [0.5]
        overs = [self._survival(p, dist, 0)]
        for k in range(1, MAX_COUNT + 1):
            s = self._survival(p, dist, k)
            lines += [float(k), k + 0.5]
            overs += [s, s]
            if s < CURVE_MIN_OVER:
                break
        overs = np.clip(np.minimum.accumulate(np.round(overs, 4)), 0.0, 1.0)
        return [{"line": float(ln), "over": float(o)}
                for ln, o in zip(lines, overs)]

    def _pass_tds_curve(self, lam: float, p: dict) -> list[dict]:
        """Poisson/NB curve at half-lines 0.5 .. 4.5 (contract shape)."""
        dist = _nb_dist(lam, p["alpha"])
        overs = np.array([self._survival(p, dist, k) for k in range(5)])
        overs = np.clip(np.minimum.accumulate(np.round(overs, 4)), 0.0, 1.0)
        return [{"line": k + 0.5, "over": float(o)}
                for k, o in enumerate(overs)]
