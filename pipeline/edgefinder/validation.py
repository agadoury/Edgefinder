"""2024 walk-forward validation harness — where ALL selection happens.

Evaluation discipline: the 2025 season is the final exam and is never used
to choose features, hyperparameters, weights, or calibration constants.
Every candidate change is scored here instead: models are fit on 2021-2023
and evaluated on held-out 2024 (features are as-of by construction, so the
2024 predictions are walk-forward), mirroring the conformal split. The
winning configuration is then baked into module constants in train.py /
features.py and the 2025 backtest is reported as-is.

Metrics are the RAW model's (no conformal layer): conformal adjustments are
themselves fit on 2024, so scoring them on 2024 would be in-sample.

Usage:
    python3 pipeline/edgefinder/validation.py --exp features
    python3 pipeline/edgefinder/validation.py --exp halflife --cache /tmp/f.pkl
    python3 pipeline/edgefinder/validation.py --exp quantreg
"""

from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))

from edgefinder import metrics  # noqa: E402
from edgefinder.conformal import CAL_TRAIN_SEASONS, calibration_mask  # noqa: E402
from edgefinder.features import (  # noqa: E402
    FEATURES,
    MARKETS,
    POSITION_FLAGS,
)
from edgefinder.train import Q_INDEX, train_market  # noqa: E402

#: the M7 additions inside qb_situation (the group predates them)
M7_FEATURES = ["qb_pass_yds_l5", "qb_pass_tds_l5", "team_pass_yds_l5"]

#: the pre-M4/M7 feature list, reconstructed for the baseline config
BASE_FEATURES = [c for c in FEATURES
                 if c not in POSITION_FLAGS and c not in M7_FEATURES]

YARD_MARKETS = ("pass_yds", "rush_yds", "rec_yds")


def eval_2024(
    frames: dict[str, pd.DataFrame],
    *,
    features: list[str] | None = None,
    half_life: float | None = None,
    log1p_markets: frozenset[str] = frozenset(),
    early_stopping: bool = False,
    mean_depth: int | None = 4,
    quantile_depth: int | None = 4,
    markets: tuple[str, ...] | None = None,
) -> dict[str, dict]:
    """Fit one config on 2021-2023, score raw predictions on 2024.

    Depths default to the production-probe winners (4/4) so single-factor
    experiments stay isolated; pass ``quantile_depth=None`` to run the
    in-training probe instead.
    """
    out: dict[str, dict] = {}
    for market in markets or tuple(MARKETS):
        frame = frames[market]
        model = train_market(
            frame, market,
            features=features,
            train_seasons=CAL_TRAIN_SEASONS,
            half_life=half_life,
            log1p=market in log1p_markets,
            early_stopping=early_stopping,
            mean_depth=mean_depth,
            quantile_depth=quantile_depth,
        )
        rows = frame[calibration_mask(frame) & frame["ref_line"].notna()]
        q = model.predict_quantiles(rows[model.features])
        proj = model.predict_projection(rows[model.features], q)
        y = rows["y"].to_numpy()
        qt = metrics.quantile_table(y, q)
        inside = (y >= q[:, Q_INDEX[0.10]]) & (y <= q[:, Q_INDEX[0.90]])
        out[market] = {
            "n": int(len(rows)),
            "mae": round(float(np.mean(np.abs(y - proj))), 3),
            "crps": metrics.crps_approx(qt),
            "coverage80": round(float(np.mean(inside)), 4),
            "quantiles": qt,
            "quantile_depth": model.train_info["quantile_depth"],
        }
    return out


def _print_config(name: str, res: dict[str, dict],
                  base: dict[str, dict] | None = None) -> None:
    print(f"\n--- {name} ---")
    print(f"{'market':<12}{'n':>6}{'mae':>9}{'crps':>9}{'cov80':>8}"
          f"{'dMAE%':>8}{'dCRPS%':>8}")
    for market, r in res.items():
        dm = dc = ""
        if base and market in base:
            dm = f"{100 * (r['mae'] / base[market]['mae'] - 1):+.2f}"
            dc = f"{100 * (r['crps'] / base[market]['crps'] - 1):+.2f}"
        print(f"{market:<12}{r['n']:>6}{r['mae']:>9.3f}{r['crps']:>9.4f}"
              f"{r['coverage80']:>8.3f}{dm:>8}{dc:>8}")


def exp_features(frames) -> None:
    """M4 (position flags) and M7 (QB/team passing form), separately+jointly."""
    m4 = BASE_FEATURES + POSITION_FLAGS
    m7 = BASE_FEATURES + M7_FEATURES
    both = BASE_FEATURES + M7_FEATURES + POSITION_FLAGS
    base = eval_2024(frames, features=BASE_FEATURES)
    _print_config("base (pre-M4/M7 features)", base)
    _print_config("M4: +position flags", eval_2024(frames, features=m4), base)
    _print_config("M7: +qb/team passing form", eval_2024(frames, features=m7), base)
    _print_config("M4+M7", eval_2024(frames, features=both), base)


def exp_halflife(frames, features: list[str] | None = None) -> None:
    """M8 recency-weight grid: half-life in {None, 3, 2, 1.5, 1} seasons."""
    base = eval_2024(frames, features=features, half_life=None)
    _print_config("uniform weights", base)
    for h in (3.0, 2.0, 1.5, 1.0):
        res = eval_2024(frames, features=features, half_life=h)
        _print_config(f"half-life {h} seasons", res, base)


def exp_quantreg(frames, features: list[str] | None = None,
                 half_life: float | None = None) -> None:
    """M11: quantile depth grid, early stopping, log1p yardage transform.

    Pre-registered decision rules (2024 only):
    * quantile depth — production keeps the in-training probe (pinball at
      q10/q90 on the 2024 holdout picks per market); this experiment just
      confirms the grid's spread.
    * early stopping — keep only if mean dCRPS% across markets <= 0.
    * log1p — keep per market only if dCRPS% < 0 and dMAE% <= +0.1
      (the projection uses p50, so the transform can move MAE too).
    """
    kw = dict(features=features, half_life=half_life)
    base = eval_2024(frames, **kw)
    _print_config("baseline (qdepth=4)", base)
    for qd in (3, 6):
        _print_config(f"quantile depth {qd}",
                      eval_2024(frames, quantile_depth=qd, **kw), base)
    _print_config("early stopping (vf=0.15)",
                  eval_2024(frames, early_stopping=True, **kw), base)
    _print_config("log1p yardage quantiles",
                  eval_2024(frames, log1p_markets=frozenset(YARD_MARKETS), **kw),
                  base)


def load_frames(cache: Path | None) -> dict[str, pd.DataFrame]:
    if cache and cache.exists():
        with cache.open("rb") as f:
            return pickle.load(f)
    from edgefinder import features as feats
    from edgefinder import load
    games = load.load_games()
    pw = load.load_player_weeks(games=games)
    frames = feats.build_all_frames(pw, games)
    if cache:
        with cache.open("wb") as f:
            pickle.dump(frames, f)
    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exp", required=True,
                        choices=["features", "halflife", "quantreg"])
    parser.add_argument("--cache", type=Path, default=None,
                        help="pickle path to cache/reuse the feature frames")
    parser.add_argument("--half-life", type=float, default=None,
                        help="half-life for the quantreg experiment")
    args = parser.parse_args()
    frames = load_frames(args.cache)
    if args.exp == "features":
        exp_features(frames)
    elif args.exp == "halflife":
        exp_halflife(frames)
    else:
        exp_quantreg(frames, half_life=args.half_life)
    return 0


if __name__ == "__main__":
    sys.exit(main())
