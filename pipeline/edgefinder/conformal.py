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

On top of the interval calibration, two more 2024-fit layers (both applied
unchanged downstream, like the conformal adjustments):

* P(over) shrinkage (M6) -- yardage markets' exported curves run
  overconfident in the high-P(over) region (2025 pre-fix: rush_yds 0.7-1.0
  bucket predicted 0.74, realized 0.64). A 2-parameter Platt map
  p' = sigmoid(a + b*logit(p)) is fit per yardage market on the 2024
  walk-forward P(over ref) predictions and applied to every exported curve
  point, so probCurve / overProbAtRef / lean / strength soften together.
  Keep/drop is decided by 2024-internal cross-validation (fit on even
  weeks, score Brier on odd weeks, and vice versa) -- a market keeps its
  shrink only when the map transfers across 2024 week halves. The map is
  strictly monotone (b > 0), so curves stay non-increasing; quantiles are
  NOT shrunk (they carry the conformal coverage guarantee).

* Confidence thresholds (M12) -- the (p75-p25)/max(p50,1) quartile cuts
  were previously calibrated on the 2025 backtest predictions (circular:
  confidence feeds strength, strength gates the reported strong-call
  sample). They are now fit here, on the 2024 walk-forward calibrated
  quantiles, persisted with provenance, and applied unchanged to 2025.

Conformity scores, shrink parameters and confidence thresholds are drawn
from 2024 rows only -- never 2025. That is enforced by
``calibration_mask`` and covered by tests/test_conformal.py.
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
    calibrate_conf_thresholds,
    fit_quantile_models,
    interp_over,
    recency_weights,
    relative_width,
    save_conf_thresholds,
    yards_prob_curve,
)

CAL_SEASON = 2024
CAL_TRAIN_SEASONS = (2021, 2022, 2023)
COUNT_MARKETS = ("receptions", "pass_tds")
#: markets whose exported P(over) curve gets the M6 Platt shrink candidate
#: (count markets already carry the mid-PIT level map)
SHRINK_MARKETS = ("pass_yds", "rush_yds", "rec_yds")
SHRINK_MIN_B = 1e-3  # monotonicity guard on the fitted slope

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


def _logit(p: np.ndarray) -> np.ndarray:
    return np.log(p / (1.0 - p))


def _apply_platt(p: np.ndarray, a: float, b: float) -> np.ndarray:
    """sigmoid(a + b*logit(p)) with exact 0/1 preserved at the endpoints."""
    p = np.asarray(p, dtype=float)
    clipped = np.clip(p, 1e-6, 1.0 - 1e-6)
    out = 1.0 / (1.0 + np.exp(-(a + max(b, SHRINK_MIN_B) * _logit(clipped))))
    return np.where(p <= 0.0, 0.0, np.where(p >= 1.0, 1.0, out))


def _fit_platt(p: np.ndarray, o: np.ndarray) -> tuple[float, float]:
    """Unpenalized 2-parameter logistic recalibration on the logit scale."""
    from sklearn.linear_model import LogisticRegression

    x = _logit(np.clip(p, 1e-4, 1.0 - 1e-4)).reshape(-1, 1)
    lr = LogisticRegression(penalty=None, solver="lbfgs", max_iter=1000)
    lr.fit(x, o.astype(int))
    return float(lr.intercept_[0]), float(lr.coef_[0][0])


def _fit_shrink(weeks: np.ndarray, p: np.ndarray, o: np.ndarray) -> dict | None:
    """M6 shrink fit with a 2024-internal transfer test.

    Pre-registered keep/drop rule: fit the Platt map on one week-parity
    half of 2024 and score Brier on the other, both directions; keep the
    market's shrink only when the mean out-of-half Brier delta improves.
    Returns the map refit on all of 2024, or None when dropped.
    """
    deltas = []
    for parity in (0, 1):
        fit_m = (weeks % 2) == parity
        if fit_m.sum() < 50 or (~fit_m).sum() < 50:
            return None
        a, b = _fit_platt(p[fit_m], o[fit_m])
        adj = _apply_platt(p[~fit_m], a, b)
        base = float(np.mean((p[~fit_m] - o[~fit_m]) ** 2))
        deltas.append(float(np.mean((adj - o[~fit_m]) ** 2)) - base)
    cross_delta = float(np.mean(deltas))
    if cross_delta >= 0.0:
        return None
    a, b = _fit_platt(p, o)
    return {"a": round(a, 4), "b": round(max(b, SHRINK_MIN_B), 4),
            "nFit": int(len(p)), "crossBrierDelta": round(cross_delta, 6)}


def fit_conformal(
    frames: dict[str, pd.DataFrame],
    models: dict,
    models_dir: Path = MODELS_DIR,
) -> "Calibrator":
    """Fit 2021-2023 models, score 2024, persist + return the calibrator.

    The calibration-model fits mirror the production training config
    (features, per-loss depths, recency half-life, log1p transform, early
    stopping) recorded in each model's train_info, so the 2024 conformity
    scores measure the same model family that ships. Also fits and
    persists the M12 confidence thresholds and the M6 P(over) shrink from
    the same 2024 walk-forward predictions.
    """
    params: dict = {
        "calSeason": CAL_SEASON,
        "calTrainSeasons": list(CAL_TRAIN_SEASONS),
        "markets": {},
    }
    cal_rows: dict[str, dict] = {}  # per-market 2024 arrays for M6/M12
    for market, frame in frames.items():
        model = models[market]
        info = getattr(model, "train_info", {}) or {}
        feats = list(getattr(model, "features", None) or FEATURES)
        depth = info.get("max_depth", 5)
        qdepth = info.get("quantile_depth", depth)
        half_life = info.get("half_life")
        log1p = bool(getattr(model, "log1p_quantiles", False))
        early_stopping = bool(info.get("early_stopping", False))

        tr = frame[calibration_train_mask(frame)]
        cal = frame[calibration_mask(frame)]
        X, y_tr = tr[feats], tr["y"].to_numpy()
        Xc, yc = cal[feats], cal["y"].to_numpy()
        w = recency_weights(tr["season"], half_life)

        if market in COUNT_MARKETS:
            mean_model = _hgb("squared_error", depth,
                              early_stopping=early_stopping).fit(
                X, y_tr, sample_weight=w)
            mean_pred = np.clip(mean_model.predict(Xc), 0.0, None)
            qpred = None
            mp = _fit_count(yc, mean_pred)
            detail = (f"lam_scale={mp['lambdaScale']:.4f} "
                      f"alpha={mp['alpha']}")
        else:
            mean_pred = None  # additive path never consumes it
            qmodels = fit_quantile_models(X, y_tr, qdepth, weights=w,
                                          log1p=log1p,
                                          early_stopping=early_stopping)
            qpred = np.column_stack([qmodels[q].predict(Xc)
                                     for q in QUANTILES])
            if log1p:
                qpred = np.expm1(qpred)
            qpred = np.sort(np.clip(qpred, 0.0, None), axis=1)
            mp = _fit_yards(yc, qpred)
            detail = (f"d10={mp['deltas']['0.10']:+.2f} "
                      f"d90={mp['deltas']['0.90']:+.2f}")
        mp["nCal"] = int(len(cal))
        params["markets"][market] = mp
        cal_rows[market] = {
            "qpred": qpred,
            "mean_pred": mean_pred,
            "y": yc,
            "week": cal["week"].to_numpy(),
            "ref_line": cal["ref_line"].to_numpy(dtype=float)
            if "ref_line" in cal else np.full(len(cal), np.nan),
        }
        print(f"conformal {market}: n_cal={mp['nCal']} "
              f"method={mp['method']} {detail}")

    # -- M12 confidence thresholds + M6 shrink, both from the same 2024
    #    walk-forward predictions the conformal layer was fit on ---------
    calib = Calibrator(params)
    thresholds: dict[str, tuple[float, float]] = {}
    for market, arr in cal_rows.items():
        quantiles = calib.quantile_matrix(market, arr["qpred"],
                                          arr["mean_pred"])
        thresholds[market] = calibrate_conf_thresholds(
            relative_width(quantiles))
        if market in SHRINK_MARKETS:
            has_ref = np.isfinite(arr["ref_line"])
            over = np.empty(int(has_ref.sum()))
            refs = arr["ref_line"][has_ref]
            for i, idx in enumerate(np.flatnonzero(has_ref)):
                curve = calib.prob_curve(market, quantiles[idx], None)
                over[i] = interp_over(curve, refs[i])
            went_over = (arr["y"][has_ref] > refs).astype(float)
            shrink = _fit_shrink(arr["week"][has_ref], over, went_over)
            if shrink is not None:
                params["markets"][market]["shrink"] = shrink
                print(f"shrink {market}: a={shrink['a']:+.3f} "
                      f"b={shrink['b']:.3f} "
                      f"crossBrierDelta={shrink['crossBrierDelta']:+.5f}")
            else:
                print(f"shrink {market}: dropped (no 2024 cross-week gain)")

    models_dir.mkdir(parents=True, exist_ok=True)
    params_path(models_dir).write_text(json.dumps(params, indent=2))
    save_conf_thresholds(thresholds, models_dir)
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
        """Calibrated P(over line) curve for one row (incl. M6 shrink)."""
        p = self.markets[market]
        if p["method"] == "additive":
            curve = yards_prob_curve(qadj_row, MARKETS[market]["step"])
            return self._shrink_curve(p, curve)
        lam = float(self._lam(p, mean_pred_i))
        if market == "pass_tds":
            return self._pass_tds_curve(lam, p)
        return self._count_curve(lam, p)

    @staticmethod
    def _shrink_curve(p: dict, curve: list[dict]) -> list[dict]:
        """Apply the market's Platt map to every curve point.

        The map is strictly increasing (b > 0), so the non-increasing
        curve invariant survives; re-rounding is followed by a cumulative
        min to keep it exact after 4-dp rounding. overProbAtRef is always
        read off the exported curve, so invariant 5 holds by construction.
        """
        sh = p.get("shrink")
        if not sh:
            return curve
        overs = _apply_platt(np.array([pt["over"] for pt in curve]),
                             sh["a"], sh["b"])
        overs = np.clip(np.minimum.accumulate(np.round(overs, 4)), 0.0, 1.0)
        return [{"line": pt["line"], "over": float(o)}
                for pt, o in zip(curve, overs)]

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
