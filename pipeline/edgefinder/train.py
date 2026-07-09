"""Per-market models: point projection, quantiles, probability curves.

Each market gets a squared-error HistGradientBoostingRegressor (point) and
seven quantile models (q = 0.05 ... 0.95). Quantiles are made monotone by
per-row sorting; the final projection is 0.5 * (mean + p50), floored at 0.

The curve builders here are the RAW (uncalibrated) primitives:
    yards      -- piecewise-linear CDF through the quantile points with
                  exponential-ish tails, sampled on the market's line step
    receptions -- same CDF machinery sampled on 0.5 steps
    pass_tds   -- Poisson(lambda) survival at half-lines
Production quantiles/curves go through conformal.Calibrator (split
conformal, fit on held-out 2024), which reuses yards_prob_curve on the
adjusted quantiles and replaces the count-market curves with a calibrated
discrete layer. `overProbAtRef` is always read off the exported curve
itself, so the contract's interpolation invariant holds by construction.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from edgefinder.features import FEATURES, MARKETS

MODELS_DIR = Path(__file__).resolve().parent.parent / "data" / "models"
TRAIN_SEASONS = (2021, 2022, 2023, 2024)
VALIDATION_SEASON = 2024  # every selection decision is scored here
QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
Q_INDEX = {q: i for i, q in enumerate(QUANTILES)}
MIN_PRIOR_PLAYED = 2  # cold-start policy: need >= 2 prior played games

#: M8 recency weighting: sample_weight = 0.5 ** (seasons_ago / half_life).
#: Chosen from the pre-registered grid {None, 3, 2, 1.5, 1} by 2024
#: walk-forward validation (validation.py --exp halflife): 3.0 gave the
#: best aggregate (mean dMAE -0.32%, dCRPS -0.24% vs uniform; improving
#: pass_yds/pass_tds/rec_yds, ~flat rush_yds/receptions). None = uniform.
#: The floor test in tests/ guards that early seasons keep real weight
#: (2021 vs a 2024-latest fit at h=3 keeps weight 0.5, never ~0).
RECENCY_HALF_LIFE: float | None = 3.0

#: M11 log1p target transform for the quantile models of these markets
#: (quantiles are equivariant under monotone maps, so back-transforming
#: with expm1 is exact). Membership decided on 2024 validation only
#: (validation.py --exp quantreg): pass_yds improved (CRPS -0.38%, MAE
#: -0.65%); rush_yds (+1.86% CRPS) and rec_yds (+0.36% CRPS) regressed
#: and stay untransformed.
LOG1P_QUANTILE_MARKETS: frozenset[str] = frozenset({"pass_yds"})

#: M11 early stopping (validation_fraction=0.15, n_iter_no_change=25) for
#: the QUANTILE models of these markets only (the mean model never
#: early-stops — the all-model ES variant hurt the pass_tds mean/lambda
#: on 2024). Membership from the 2024 marginal-effect run, kept where
#: dCRPS <= 0 and dMAE <= +0.1% given the rest of the M11 config:
#: pass_yds (-1.42% MAE, -0.56% CRPS) and rush_yds (-0.12%, -0.09%) kept;
#: pass_tds (+1.33%/+1.35%), rec_yds (dCRPS +0.07%) and receptions
#: (dMAE +0.21%) dropped.
QUANTILE_ES_MARKETS: frozenset[str] = frozenset({"pass_yds", "rush_yds"})

#: M11 depth grids for the per-loss probes (scored on the 2024 holdout:
#: MAE for the mean model, mean pinball at q10/q90 for the quantile models)
MEAN_DEPTH_GRID = (4, 6)
QUANTILE_DEPTH_GRID = (3, 4, 6)

LEAN_BAND = 0.04
CONF_MULT = {"high": 1.0, "medium": 0.85, "low": 0.7}


@dataclass
class MarketModel:
    """Trained artifacts for one market."""

    market: str
    mean_model: HistGradientBoostingRegressor
    quantile_models: dict[float, HistGradientBoostingRegressor]
    features: list[str]
    pos_medians: dict[str, dict[str, float]]  # pos -> feature -> median
    train_info: dict = field(default_factory=dict)
    log1p_quantiles: bool = False  # quantile models fit on log1p(y)

    def predict_quantiles(self, X: pd.DataFrame) -> np.ndarray:
        """(n, 7) matrix of monotone (row-sorted) quantile predictions.

        When the quantile models were fit on log1p(y) the predictions are
        mapped back with expm1 — exact for quantiles, which are equivariant
        under monotone transforms.
        """
        preds = np.column_stack(
            [self.quantile_models[q].predict(X[self.features]) for q in QUANTILES]
        )
        if self.log1p_quantiles:
            preds = np.expm1(preds)
        return np.sort(np.clip(preds, 0.0, None), axis=1)

    def predict_projection(
        self, X: pd.DataFrame, quantiles: np.ndarray | None = None
    ) -> np.ndarray:
        """0.5 * (mean model + p50), floored at 0."""
        if quantiles is None:
            quantiles = self.predict_quantiles(X)
        mean = self.mean_model.predict(X[self.features])
        p50 = quantiles[:, Q_INDEX[0.50]]
        return np.clip(0.5 * (mean + p50), 0.0, None)


def _hgb(loss: str, max_depth: int, quantile: float | None = None,
         early_stopping: bool = False) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss=loss,
        quantile=quantile,
        learning_rate=0.06,
        max_iter=400,
        max_depth=max_depth,
        max_leaf_nodes=31,
        min_samples_leaf=40,
        l2_regularization=1.0,
        early_stopping=early_stopping,
        validation_fraction=0.15,
        n_iter_no_change=25,
        scoring="loss",
        random_state=7,
    )


def recency_weights(
    seasons: pd.Series | np.ndarray,
    half_life: float | None = RECENCY_HALF_LIFE,
    latest: int | None = None,
) -> np.ndarray:
    """M8 exponential recency weights: 0.5 ** (seasons_ago / half_life).

    ``latest`` defaults to the newest season present, so the same half-life
    means the same *relative* decay whether the fit covers 2021-2023
    (calibration/validation split) or 2021-2024 (production). Weights are
    strictly positive by construction — early seasons are down-weighted,
    never dropped. ``half_life=None`` returns uniform weights.
    """
    s = np.asarray(seasons, dtype=float)
    if half_life is None:
        return np.ones(len(s))
    if half_life <= 0:
        raise ValueError("half_life must be positive (or None for uniform)")
    ref = float(latest if latest is not None else s.max())
    return 0.5 ** ((ref - s) / half_life)


def training_mask(
    frame: pd.DataFrame, seasons: tuple[int, ...] = TRAIN_SEASONS
) -> pd.Series:
    """Rows usable as targets: train seasons, played, eligible, has history."""
    return (
        frame["season"].isin(seasons)
        & frame["played"]
        & frame["eligible"]
        & (frame["prior_played"] >= MIN_PRIOR_PLAYED)
        & frame["y"].notna()
    )


def _quantile_target(y: np.ndarray, log1p: bool) -> np.ndarray:
    return np.log1p(np.clip(y, 0.0, None)) if log1p else y


def fit_quantile_models(
    X: pd.DataFrame,
    y: np.ndarray,
    depth: int,
    weights: np.ndarray | None = None,
    log1p: bool = False,
    early_stopping: bool = False,
) -> dict[float, HistGradientBoostingRegressor]:
    """The seven quantile models (shared by production and calibration fits)."""
    target = _quantile_target(y, log1p)
    return {
        q: _hgb("quantile", depth, quantile=q, early_stopping=early_stopping)
        .fit(X, target, sample_weight=weights)
        for q in QUANTILES
    }


def _pinball(y: np.ndarray, pred: np.ndarray, tau: float) -> float:
    d = y - pred
    return float(np.mean(np.maximum(tau * d, (tau - 1.0) * d)))


def train_market(
    frame: pd.DataFrame,
    market: str,
    *,
    features: list[str] | None = None,
    train_seasons: tuple[int, ...] = TRAIN_SEASONS,
    half_life: float | None = RECENCY_HALF_LIFE,
    log1p: bool | None = None,
    early_stopping: bool | None = None,
    mean_depth: int | None = None,
    quantile_depth: int | None = None,
) -> MarketModel:
    """Fit mean + quantile models with per-loss depth probes (M11).

    Depth probes fit on the pre-2024 seasons and score on the held-out
    VALIDATION_SEASON (2024): the mean depth by MAE (grid MEAN_DEPTH_GRID),
    the quantile depth by mean pinball at q=0.10/0.90 (QUANTILE_DEPTH_GRID).
    The winners are refit on all ``train_seasons``. Recency weights (M8)
    and the log1p quantile transform (M11) apply to probes and final fits
    alike. ``early_stopping`` regularizes the QUANTILE models only (M11's
    scope) — the mean model always trains without it, because the 2024
    experiment showed ES helping the quantile losses while nudging the
    count-market mean (and therefore the NB lambda) the wrong way.
    Explicit ``mean_depth``/``quantile_depth`` skip the probes — used by
    the validation harness to isolate single factors.
    """
    features = list(FEATURES) if features is None else list(features)
    if log1p is None:
        log1p = market in LOG1P_QUANTILE_MARKETS
    if early_stopping is None:
        early_stopping = market in QUANTILE_ES_MARKETS
    rows = frame[training_mask(frame, train_seasons)]
    X, y = rows[features], rows["y"].to_numpy()
    w = recency_weights(rows["season"], half_life)

    holdout = (rows["season"] == VALIDATION_SEASON).to_numpy()
    can_probe = holdout.sum() > 200 and (~holdout).sum() > 500
    Xf, yf, wf = X[~holdout], y[~holdout], w[~holdout]
    Xh, yh = X[holdout], y[holdout]

    best_mae: float | None = None
    if mean_depth is None:
        mean_depth, best_mae = 5, math.inf
        if can_probe:
            for depth in MEAN_DEPTH_GRID:
                probe = _hgb("squared_error", depth)
                probe.fit(Xf, yf, sample_weight=wf)
                mae = mean_absolute_error(yh, probe.predict(Xh))
                if mae < best_mae:
                    mean_depth, best_mae = depth, mae

    best_pin: float | None = None
    if quantile_depth is None:
        quantile_depth, best_pin = mean_depth, math.inf
        if can_probe:
            for depth in QUANTILE_DEPTH_GRID:
                pins = []
                for tau in (0.10, 0.90):
                    probe = _hgb("quantile", depth, quantile=tau,
                                 early_stopping=early_stopping)
                    probe.fit(Xf, _quantile_target(yf, log1p), sample_weight=wf)
                    pred = probe.predict(Xh)
                    if log1p:
                        pred = np.expm1(pred)
                    pins.append(_pinball(yh, np.clip(pred, 0.0, None), tau))
                pin = float(np.mean(pins))
                if pin < best_pin:
                    quantile_depth, best_pin = depth, pin

    mean_model = _hgb("squared_error", mean_depth).fit(X, y, sample_weight=w)
    quantile_models = fit_quantile_models(
        X, y, quantile_depth, weights=w, log1p=log1p,
        early_stopping=early_stopping,
    )

    pos_medians: dict[str, dict[str, float]] = {}
    for pos, grp in rows.groupby("pos"):
        pos_medians[str(pos)] = grp[features].median().to_dict()
    pos_medians["__all__"] = rows[features].median().to_dict()

    info = {
        "n_train": int(len(rows)),
        "max_depth": mean_depth,
        "quantile_depth": quantile_depth,
        "half_life": half_life,
        "log1p_quantiles": log1p,
        "early_stopping": early_stopping,
        "holdout_2024_mae": None if best_mae in (None, math.inf)
        else round(best_mae, 3),
        "holdout_2024_pinball": None if best_pin in (None, math.inf)
        else round(best_pin, 4),
    }
    return MarketModel(market, mean_model, quantile_models, features,
                       pos_medians, info, log1p_quantiles=log1p)


def train_all(
    frames: dict[str, pd.DataFrame], models_dir: Path = MODELS_DIR
) -> dict[str, MarketModel]:
    models_dir.mkdir(parents=True, exist_ok=True)
    models: dict[str, MarketModel] = {}
    for market, frame in frames.items():
        model = train_market(frame, market)
        joblib.dump(model, models_dir / f"{market}.joblib")
        models[market] = model
        print(f"trained {market}: n={model.train_info['n_train']} "
              f"depth={model.train_info['max_depth']}"
              f"/q{model.train_info['quantile_depth']} "
              f"hl={model.train_info['half_life']} "
              f"log1p={model.train_info['log1p_quantiles']} "
              f"holdout2024mae={model.train_info['holdout_2024_mae']}")
    return models


def load_models(models_dir: Path = MODELS_DIR) -> dict[str, MarketModel]:
    return {
        m: joblib.load(models_dir / f"{m}.joblib")
        for m in MARKETS
        if (models_dir / f"{m}.joblib").exists()
    }


# ---------------------------------------------------------------------------
# probability curves
# ---------------------------------------------------------------------------

def _cdf_nodes(qvals: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Piecewise-linear CDF nodes through the 7 quantiles + p02/p98 tails.

    Tail points extend linearly at a decayed slope (exponential-ish tail
    matched to the adjacent segment's scale).
    """
    ps = np.array(QUANTILES)
    vs = np.maximum.accumulate(qvals.astype(float))
    # strictify so the CDF is invertible even with tied quantiles
    for i in range(1, len(vs)):
        if vs[i] <= vs[i - 1]:
            vs[i] = vs[i - 1] + 1e-6
    # Un-collapse a degenerate upper tail: when the raw p95 crosses below p90
    # the monotone sort clamps it to p90 + 1e-6, which would concentrate 5% of
    # the probability mass in a sliver and render as a spike at the curve's
    # right edge. Floor the p90..p95 segment at 35% of the p75..p90 span
    # (a normal distribution has ~60%). The low side is left alone — mass
    # piling up at 0 (low-usage weeks) is real zero-inflation, not an artifact.
    hi_floor = 0.35 * max(vs[-2] - vs[-3], 0.0)
    if vs[-1] - vs[-2] < hi_floor:
        vs[-1] = vs[-2] + hi_floor
    b_lo = max(vs[1] - vs[0], 1e-6)   # p05..p10 scale
    b_hi = max(vs[-1] - vs[-2], 1e-6)  # p90..p95 scale
    v02 = vs[0] + b_lo * math.log(0.02 / 0.05)  # < v05
    v98 = vs[-1] + b_hi * math.log(0.05 / 0.02)  # > v95
    ps = np.concatenate([[0.02], ps, [0.98]])
    vs = np.concatenate([[v02], vs, [v98]])
    return vs, ps


def _over_at(vs: np.ndarray, ps: np.ndarray, line: float) -> float:
    """1 - CDF(line) with clamping outside the node range."""
    return float(1.0 - np.interp(line, vs, ps))


def yards_prob_curve(qvals: np.ndarray, line_step: float) -> list[dict]:
    """Dense P(over line) curve on the market's line step across ~p02-p98."""
    vs, ps = _cdf_nodes(qvals)
    lo = max(line_step, math.floor(vs[0] / line_step) * line_step)
    hi = math.ceil(vs[-1] / line_step) * line_step
    step = line_step
    while (hi - lo) / step > 80:
        step += line_step
    if hi - lo < 2 * step:
        hi = lo + 2 * step
    lines = np.round(np.arange(lo, hi + step / 2, step), 2)
    over = np.array([_over_at(vs, ps, ln) for ln in lines])
    over = np.minimum.accumulate(np.round(over, 4))
    over = np.clip(over, 0.0, 1.0)
    return [{"line": float(ln), "over": float(o)} for ln, o in zip(lines, over)]


def receptions_prob_curve(qvals: np.ndarray) -> list[dict]:
    """Receptions curve on 0.5-steps through the quantile CDF."""
    return yards_prob_curve(qvals, 0.5)


def _poisson_sf(k: int, lam: float) -> float:
    """P(N > k) = P(N >= k + 1) for N ~ Poisson(lam)."""
    term, cdf = math.exp(-lam), math.exp(-lam)
    for i in range(1, k + 1):
        term *= lam / i
        cdf += term
    return max(0.0, 1.0 - cdf)


def pass_tds_prob_curve(projection: float) -> list[dict]:
    """Poisson curve at half-lines 0.5 .. 4.5."""
    lam = max(0.05, float(projection))
    curve = []
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        over = round(_poisson_sf(int(line), lam), 4)
        curve.append({"line": line, "over": over})
    for i in range(1, len(curve)):  # guard against rounding blips
        curve[i]["over"] = min(curve[i]["over"], curve[i - 1]["over"])
    return curve


def build_prob_curve(
    market: str, qvals: np.ndarray, projection: float
) -> list[dict]:
    if market == "pass_tds":
        return pass_tds_prob_curve(projection)
    if market == "receptions":
        return receptions_prob_curve(qvals)
    return yards_prob_curve(qvals, MARKETS[market]["step"])


def interp_over(curve: list[dict], line: float) -> float:
    """The frontend's rule: linear interp on the curve, clamped at the ends."""
    lines = np.array([p["line"] for p in curve])
    overs = np.array([p["over"] for p in curve])
    return float(np.interp(line, lines, overs))


# ---------------------------------------------------------------------------
# lean / strength / confidence
# ---------------------------------------------------------------------------

def lean_of(over_prob: float) -> str:
    if over_prob - 0.5 >= LEAN_BAND:
        return "over"
    if 0.5 - over_prob >= LEAN_BAND:
        return "under"
    return "neutral"


def strength_of(over_prob: float, confidence: str) -> int:
    edge = 2.0 * abs(over_prob - 0.5) * CONF_MULT[confidence]
    return int(round(100 * min(1.0, edge)))


def relative_width(quantiles: np.ndarray) -> np.ndarray:
    """(p75 - p25) / max(p50, 1) -- the confidence raw signal."""
    p25 = quantiles[:, Q_INDEX[0.25]]
    p50 = quantiles[:, Q_INDEX[0.50]]
    p75 = quantiles[:, Q_INDEX[0.75]]
    return (p75 - p25) / np.maximum(p50, 1.0)


def calibrate_conf_thresholds(rw: np.ndarray) -> tuple[float, float]:
    """25th/75th percentiles of relative width => ~25/50/25 split."""
    lo, hi = np.nanpercentile(rw, [25, 75])
    return float(lo), float(hi)


def confidence_of(
    rw: float, games_played_season: float, thresholds: tuple[float, float]
) -> str:
    lo, hi = thresholds
    if rw <= lo:
        level = "high"
    elif rw <= hi:
        level = "medium"
    else:
        level = "low"
    if games_played_season < 5:  # thin current-season sample: knock one level
        level = {"high": "medium", "medium": "low", "low": "low"}[level]
    return level


#: M12: thresholds must be fit out-of-sample. The only accepted provenance
#: is the 2024 walk-forward split (models fit on 2021-2023, scored on 2024)
#: — never the 2025 evaluation predictions, which would be circular.
CONF_THRESHOLDS_SOURCE = "2024_walkforward"


def save_conf_thresholds(
    thresholds: dict[str, tuple[float, float]],
    models_dir: Path = MODELS_DIR,
    source: str = CONF_THRESHOLDS_SOURCE,
) -> None:
    """Persist per-market (lo, hi) relative-width thresholds + provenance."""
    path = models_dir / "confidence_thresholds.json"
    path.write_text(json.dumps({
        "source": source,
        "calSeason": VALIDATION_SEASON,
        "thresholds": {m: [round(a, 5), round(b, 5)]
                       for m, (a, b) in thresholds.items()},
    }, indent=2))


def load_conf_thresholds(
    models_dir: Path = MODELS_DIR,
) -> dict[str, tuple[float, float]]:
    data = json.loads((models_dir / "confidence_thresholds.json").read_text())
    if data.get("source") != CONF_THRESHOLDS_SOURCE:
        raise ValueError(
            "confidence_thresholds.json provenance is "
            f"{data.get('source')!r}; expected {CONF_THRESHOLDS_SOURCE!r} "
            "(M12: thresholds must come from the 2024 walk-forward split)"
        )
    return {m: (v[0], v[1]) for m, v in data["thresholds"].items()}
