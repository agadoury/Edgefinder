"""Walk-forward 2025 evaluation of the 2021-2024-trained models.

Rows evaluated: 2025 REG weeks 1..(demo_week-1), played + eligible, with at
least MIN_PRIOR_PLAYED prior career games and a computable reference line.
Features are as-of by construction, so 2025 history enters only from
earlier weeks. Also calibrates the per-market confidence thresholds
(roughly 25/50/25) and persists per-row predictions for `modelHistory`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from edgefinder.features import FEATURES
from edgefinder.train import (
    MODELS_DIR,
    MIN_PRIOR_PLAYED,
    MarketModel,
    Q_INDEX,
    build_prob_curve,
    calibrate_conf_thresholds,
    confidence_of,
    interp_over,
    lean_of,
    relative_width,
    save_conf_thresholds,
    strength_of,
)

CAL_EDGES = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0)
STRONG_CALL_MIN = 60


def eval_mask(frame: pd.DataFrame, demo_week: int) -> pd.Series:
    return (
        (frame["season"] == 2025)
        & (frame["week"] < demo_week)
        & frame["played"]
        & frame["eligible"]
        & (frame["prior_played"] >= MIN_PRIOR_PLAYED)
        & frame["ref_line"].notna()
    )


def predict_rows(rows: pd.DataFrame, model: MarketModel, market: str) -> pd.DataFrame:
    """Projection, quantiles, curve prob at ref line, and raw width per row."""
    quantiles = model.predict_quantiles(rows[FEATURES])
    projection = model.predict_projection(rows[FEATURES], quantiles)
    over_ref = np.empty(len(rows))
    for i, (_, row) in enumerate(rows.iterrows()):
        curve = build_prob_curve(market, quantiles[i], projection[i])
        over_ref[i] = interp_over(curve, float(row["ref_line"]))
    out = rows[["season", "week", "player_id", "name", "pos", "team", "opp",
                "game_id", "y", "ref_line", "ref_blend",
                "games_played_season"]].copy()
    out["projection"] = projection
    out["over_prob"] = over_ref
    out["rw"] = relative_width(quantiles)
    for q, i in Q_INDEX.items():
        out[f"p{int(q * 100):02d}"] = quantiles[:, i]
    return out


def _calibration_buckets(preds: pd.DataFrame) -> list[dict]:
    over_actual = (preds["y"] > preds["ref_line"]).astype(float)
    buckets = []
    for lo, hi in zip(CAL_EDGES[:-1], CAL_EDGES[1:]):
        m = (preds["over_prob"] >= lo) & (
            preds["over_prob"] < hi if hi < 1.0 else preds["over_prob"] <= hi
        )
        n = int(m.sum())
        buckets.append({
            "bucketMid": round((lo + hi) / 2, 2),
            "predicted": round(float(preds.loc[m, "over_prob"].mean()), 3) if n else None,
            "actual": round(float(over_actual[m].mean()), 3) if n else None,
            "n": n,
        })
    return buckets


def evaluate_market(preds: pd.DataFrame) -> dict:
    """Contract-shaped metrics for one market's prediction rows."""
    y = preds["y"].to_numpy()
    mae = float(np.mean(np.abs(y - preds["projection"])))
    baseline_mae = float(np.mean(np.abs(y - preds["ref_blend"])))
    inside = (y >= preds["p10"].to_numpy()) & (y <= preds["p90"].to_numpy())
    coverage80 = float(np.mean(inside))

    strong = preds[(preds["strength"] >= STRONG_CALL_MIN)
                   & (preds["lean"] != "neutral")
                   & (preds["y"] != preds["ref_line"])]  # exclude pushes
    if len(strong):
        went_over = strong["y"] > strong["ref_line"]
        hit = np.where(strong["lean"] == "over", went_over, ~went_over)
        strong_rate = float(np.mean(hit))
    else:
        strong_rate = None
    return {
        "n": int(len(preds)),
        "mae": round(mae, 2),
        "baselineMae": round(baseline_mae, 2),
        "coverage80": round(coverage80, 3),
        "strongCallHitRate": None if strong_rate is None else round(strong_rate, 3),
        "strongCallN": int(len(strong)),
        "calibration": _calibration_buckets(preds),
    }


def run_backtest(
    frames: dict[str, pd.DataFrame],
    models: dict[str, MarketModel],
    demo_week: int,
    models_dir: Path = MODELS_DIR,
) -> dict:
    """Evaluate every market; persist thresholds + per-row predictions.

    Returns the contract's `backtest.byMarket` dict.
    """
    all_preds = []
    thresholds: dict[str, tuple[float, float]] = {}
    by_market: dict[str, dict] = {}

    for market, frame in frames.items():
        rows = frame[eval_mask(frame, demo_week)]
        preds = predict_rows(rows, models[market], market)
        thresholds[market] = calibrate_conf_thresholds(preds["rw"].to_numpy())
        preds["confidence"] = [
            confidence_of(rw, gp, thresholds[market])
            for rw, gp in zip(preds["rw"], preds["games_played_season"])
        ]
        preds["lean"] = preds["over_prob"].map(lean_of)
        preds["strength"] = [
            strength_of(p, c) for p, c in zip(preds["over_prob"], preds["confidence"])
        ]
        preds["market"] = market
        all_preds.append(preds)
        by_market[market] = evaluate_market(preds)

    save_conf_thresholds(thresholds, models_dir)
    combined = pd.concat(all_preds, ignore_index=True)
    combined.to_csv(models_dir / "backtest_predictions.csv", index=False)
    return by_market


def print_report(by_market: dict[str, dict]) -> None:
    header = (f"{'market':<12}{'n':>6}{'mae':>9}{'baseMae':>9}"
              f"{'cov80':>8}{'strongHit':>11}{'strongN':>9}")
    print("\n=== backtest: 2025 walk-forward ===")
    print(header)
    print("-" * len(header))
    for market, m in by_market.items():
        hit = "-" if m["strongCallHitRate"] is None else f"{m['strongCallHitRate']:.3f}"
        print(f"{market:<12}{m['n']:>6}{m['mae']:>9.2f}{m['baselineMae']:>9.2f}"
              f"{m['coverage80']:>8.3f}{hit:>11}{m['strongCallN']:>9}")
    print("\ncalibration (P(over ref) buckets):")
    for market, m in by_market.items():
        cells = []
        for b in m["calibration"]:
            if b["n"]:
                cells.append(f"[{b['bucketMid']:.2f}] pred {b['predicted']:.2f} "
                             f"act {b['actual']:.2f} n={b['n']}")
        print(f"  {market}: " + " | ".join(cells))
