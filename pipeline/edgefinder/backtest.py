"""Walk-forward 2025 evaluation of the 2021-2024-trained models.

Rows evaluated: 2025 REG weeks 1..(demo_week-1), played + eligible, with at
least MIN_PRIOR_PLAYED prior career games and a computable reference line.
Features are as-of by construction, so 2025 history enters only from
earlier weeks. Intervals and probability curves go through the split
conformal calibrator (fit on 2024 only -- see conformal.py); confidence
thresholds are likewise loaded from the 2024 walk-forward fit (M12), so
2025 is pure evaluation -- nothing here is tuned on it. Persists per-row
predictions for `modelHistory`.

Metrics per market (M3): MAE vs the refLine-blend baseline, central-80%
coverage, per-quantile empirical coverage and pinball loss, a CRPS
approximation, Brier score for P(over ref), calibration buckets with
drift summaries, and the strong-call hit rate with a Wilson 95% interval.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from edgefinder import metrics
from edgefinder.conformal import Calibrator
from edgefinder.train import (
    MODELS_DIR,
    MIN_PRIOR_PLAYED,
    MarketModel,
    Q_INDEX,
    QUANTILES,
    confidence_of,
    interp_over,
    lean_of,
    relative_width,
    strength_of,
)

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


def predict_rows(
    rows: pd.DataFrame, model: MarketModel, market: str, calib: Calibrator
) -> pd.DataFrame:
    """Projection, calibrated quantiles/curve prob at ref, raw width per row.

    The point projection stays the raw mean/median blend (untouched by
    interval calibration); quantiles and curves are the conformal-adjusted
    ones (curves include the M6 shrink where fitted). Count-market curves
    take the mean-model expectation as lambda, not the blend (the blend's
    count median runs ~0.15 TD low).
    """
    raw_q = model.predict_quantiles(rows[model.features])
    projection = model.predict_projection(rows[model.features], raw_q)
    mean_pred = np.clip(model.mean_model.predict(rows[model.features]),
                        0.0, None)
    quantiles = calib.quantile_matrix(market, raw_q, mean_pred)
    over_ref = np.empty(len(rows))
    for i, (_, row) in enumerate(rows.iterrows()):
        curve = calib.prob_curve(market, quantiles[i], mean_pred[i])
        over_ref[i] = interp_over(curve, float(row["ref_line"]))
    out = rows[["season", "week", "player_id", "name", "pos", "team", "opp",
                "game_id", "y", "ref_line", "ref_blend",
                "games_played_season"]].copy()
    out["projection"] = projection
    out["over_prob"] = over_ref
    out["rw"] = relative_width(quantiles)
    # persisted so downstream evaluation (e.g. the M13 FanDuel benchmark)
    # can rebuild the exact calibrated curve at arbitrary lines: count-
    # market curves are a function of the mean prediction, not quantiles
    out["mean_pred"] = mean_pred
    for q, i in Q_INDEX.items():
        out[f"p{int(q * 100):02d}"] = quantiles[:, i]
    return out


def evaluate_market(preds: pd.DataFrame) -> dict:
    """Contract metrics plus the M3 distributional diagnostics.

    The contract keys (n, mae, baselineMae, coverage80, strongCallHitRate,
    strongCallN, calibration) are exported to meta.json; the extended keys
    feed the run report and the 2024-vs-2025 comparisons only.
    """
    y = preds["y"].to_numpy()
    mae = float(np.mean(np.abs(y - preds["projection"])))
    baseline_mae = float(np.mean(np.abs(y - preds["ref_blend"])))
    qmat = np.column_stack(
        [preds[f"p{int(q * 100):02d}"].to_numpy() for q in QUANTILES]
    )
    inside = (y >= qmat[:, Q_INDEX[0.10]]) & (y <= qmat[:, Q_INDEX[0.90]])
    coverage80 = float(np.mean(inside))
    qtable = metrics.quantile_table(y, qmat)

    went_over = (preds["y"] > preds["ref_line"]).to_numpy().astype(float)
    over_prob = preds["over_prob"].to_numpy()
    buckets = metrics.calibration_buckets(over_prob, went_over)

    strong = preds[(preds["strength"] >= STRONG_CALL_MIN)
                   & (preds["lean"] != "neutral")
                   & (preds["y"] != preds["ref_line"])]  # exclude pushes
    if len(strong):
        strong_over = strong["y"] > strong["ref_line"]
        hit = np.where(strong["lean"] == "over", strong_over, ~strong_over)
        strong_rate = float(np.mean(hit))
        wilson = metrics.wilson_interval(int(hit.sum()), len(strong))
    else:
        strong_rate, wilson = None, None
    return {
        # -- contract keys (meta.json backtest.byMarket) ------------------
        "n": int(len(preds)),
        "mae": round(mae, 2),
        "baselineMae": round(baseline_mae, 2),
        "coverage80": round(coverage80, 3),
        "strongCallHitRate": None if strong_rate is None else round(strong_rate, 3),
        "strongCallN": int(len(strong)),
        "calibration": buckets,
        # -- extended diagnostics (report only, M3) -----------------------
        "quantiles": qtable,
        "crps": metrics.crps_approx(qtable),
        "brier": round(metrics.brier_score(over_prob, went_over), 5),
        "bucketDrift": metrics.bucket_drift(buckets),
        "strongCallWilson95": None if wilson is None
        else [round(wilson[0], 3), round(wilson[1], 3)],
    }


def run_backtest(
    frames: dict[str, pd.DataFrame],
    models: dict[str, MarketModel],
    demo_week: int,
    calib: Calibrator,
    thresholds: dict[str, tuple[float, float]],
    models_dir: Path = MODELS_DIR,
) -> dict:
    """Evaluate every market with the fixed 2024-fit thresholds.

    ``thresholds`` come from conformal.fit_conformal's 2024 walk-forward
    predictions (M12) -- they are applied here, never refit on 2025.
    Persists per-row predictions and returns `backtest.byMarket`.
    """
    all_preds = []
    by_market: dict[str, dict] = {}

    for market, frame in frames.items():
        rows = frame[eval_mask(frame, demo_week)]
        preds = predict_rows(rows, models[market], market, calib)
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

    combined = pd.concat(all_preds, ignore_index=True)
    combined.to_csv(models_dir / "backtest_predictions.csv", index=False)
    return by_market


def print_report(by_market: dict[str, dict]) -> None:
    header = (f"{'market':<12}{'n':>6}{'mae':>9}{'baseMae':>9}{'cov80':>8}"
              f"{'crps':>9}{'brier':>9}{'strongHit':>11}{'strongN':>9}")
    print("\n=== backtest: 2025 walk-forward ===")
    print(header)
    print("-" * len(header))
    for market, m in by_market.items():
        hit = "-" if m["strongCallHitRate"] is None else f"{m['strongCallHitRate']:.3f}"
        print(f"{market:<12}{m['n']:>6}{m['mae']:>9.2f}{m['baselineMae']:>9.2f}"
              f"{m['coverage80']:>8.3f}{m['crps']:>9.3f}{m['brier']:>9.4f}"
              f"{hit:>11}{m['strongCallN']:>9}")

    print("\nper-quantile empirical coverage (target = tau) and pinball:")
    for market, m in by_market.items():
        cov = " ".join(f"{k}={v['coverage']:.3f}" for k, v in m["quantiles"].items())
        print(f"  {market}: {cov}")
        pin = " ".join(f"{k}={v['pinball']:.3f}" for k, v in m["quantiles"].items())
        print(f"  {' ' * len(market)}  pinball {pin}")

    print("\ncalibration (P(over ref) buckets; drift = |pred - act|):")
    for market, m in by_market.items():
        cells = []
        for b in m["calibration"]:
            if b["n"]:
                cells.append(f"[{b['bucketMid']:.2f}] pred {b['predicted']:.2f} "
                             f"act {b['actual']:.2f} n={b['n']}")
        drift = m["bucketDrift"]
        print(f"  {market}: " + " | ".join(cells))
        print(f"  {' ' * len(market)}  worst drift {drift['worst']:.3f}, "
              f"mean drift {drift['mean']:.3f}")
