"""Per-market models: point projection, quantiles, probability curves.

Each market gets a squared-error HistGradientBoostingRegressor (point) and
seven quantile models (q = 0.05 ... 0.95). Quantiles are made monotone by
per-row sorting; the final projection is 0.5 * (mean + p50), floored at 0.

Probability curves:
    yards      -- piecewise-linear CDF through the quantile points with
                  exponential-ish tails, sampled on the market's line step
    receptions -- same CDF machinery sampled on 0.5 steps
    pass_tds   -- Poisson(lambda = max(0.05, projection)) at half-lines
`overProbAtRef` is always read off the exported curve itself, so the
contract's interpolation invariant holds by construction.
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
QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
Q_INDEX = {q: i for i, q in enumerate(QUANTILES)}
MIN_PRIOR_PLAYED = 2  # cold-start policy: need >= 2 prior played games

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

    def predict_quantiles(self, X: pd.DataFrame) -> np.ndarray:
        """(n, 7) matrix of monotone (row-sorted) quantile predictions."""
        preds = np.column_stack(
            [self.quantile_models[q].predict(X[self.features]) for q in QUANTILES]
        )
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


def _hgb(loss: str, max_depth: int, quantile: float | None = None
         ) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss=loss,
        quantile=quantile,
        learning_rate=0.06,
        max_iter=400,
        max_depth=max_depth,
        max_leaf_nodes=31,
        min_samples_leaf=40,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=7,
    )


def training_mask(frame: pd.DataFrame) -> pd.Series:
    """Rows usable as targets: train seasons, played, eligible, has history."""
    return (
        frame["season"].isin(TRAIN_SEASONS)
        & frame["played"]
        & frame["eligible"]
        & (frame["prior_played"] >= MIN_PRIOR_PLAYED)
        & frame["y"].notna()
    )


def train_market(frame: pd.DataFrame, market: str) -> MarketModel:
    """Fit mean + quantile models with a small depth sanity grid.

    Grid: max_depth in {4, 6} scored by mean-model MAE with 2024 held out;
    the winner is refit on all four training seasons.
    """
    rows = frame[training_mask(frame)]
    X, y = rows[FEATURES], rows["y"].to_numpy()

    holdout = rows["season"] == 2024
    best_depth, best_mae = 5, math.inf
    if holdout.sum() > 200 and (~holdout).sum() > 500:
        for depth in (4, 6):
            probe = _hgb("squared_error", depth)
            probe.fit(X[~holdout.to_numpy()], y[~holdout.to_numpy()])
            mae = mean_absolute_error(
                y[holdout.to_numpy()], probe.predict(X[holdout.to_numpy()])
            )
            if mae < best_mae:
                best_depth, best_mae = depth, mae

    mean_model = _hgb("squared_error", best_depth).fit(X, y)
    quantile_models = {
        q: _hgb("quantile", best_depth, quantile=q).fit(X, y) for q in QUANTILES
    }

    pos_medians: dict[str, dict[str, float]] = {}
    for pos, grp in rows.groupby("pos"):
        pos_medians[str(pos)] = grp[FEATURES].median().to_dict()
    pos_medians["__all__"] = rows[FEATURES].median().to_dict()

    info = {
        "n_train": int(len(rows)),
        "max_depth": best_depth,
        "holdout_2024_mae": None if best_mae is math.inf else round(best_mae, 3),
    }
    return MarketModel(market, mean_model, quantile_models, list(FEATURES),
                       pos_medians, info)


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
              f"depth={model.train_info['max_depth']} "
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


def save_conf_thresholds(
    thresholds: dict[str, tuple[float, float]], models_dir: Path = MODELS_DIR
) -> None:
    path = models_dir / "confidence_thresholds.json"
    path.write_text(json.dumps(
        {m: [round(a, 5), round(b, 5)] for m, (a, b) in thresholds.items()},
        indent=2,
    ))


def load_conf_thresholds(models_dir: Path = MODELS_DIR) -> dict[str, tuple[float, float]]:
    data = json.loads((models_dir / "confidence_thresholds.json").read_text())
    return {m: (v[0], v[1]) for m, v in data.items()}
