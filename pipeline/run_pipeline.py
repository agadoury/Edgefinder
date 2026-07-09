#!/usr/bin/env python3
"""EdgeFinder pipeline orchestrator.

Runs download -> load -> features -> train -> backtest -> export -> validate
and leaves the contract JSON in pipeline/data/export (the staging dir; the
web app's copy is a separate step).

Usage:
    python3 pipeline/run_pipeline.py [--demo-week 14] [--skip-download]
                                     [--retrain] [--export-dir PATH]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPELINE_DIR))

from edgefinder import backtest as bt  # noqa: E402
from edgefinder import conformal  # noqa: E402
from edgefinder import export as ex  # noqa: E402
from edgefinder import features, load, train, validate  # noqa: E402
from edgefinder.download import download_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-week", type=int, default=14,
                        help="preferred 2025 demo week (verified, may shift)")
    parser.add_argument("--skip-download", action="store_true",
                        help="trust the raw cache, skip the fetch step")
    parser.add_argument("--retrain", action="store_true",
                        help="retrain even when saved models exist")
    parser.add_argument("--export-dir", type=Path, default=ex.EXPORT_DIR)
    args = parser.parse_args()

    t0 = time.time()

    if not args.skip_download:
        print("== download ==")
        download_all()

    print("== load ==")
    games = load.load_games()
    pw = load.load_player_weeks(games=games)
    print(f"{len(games)} games, {len(pw)} player-weeks")

    print("== features ==")
    frames = features.build_all_frames(pw, games)
    for market, frame in frames.items():
        print(f"{market}: {len(frame)} rows, {int(frame['eligible'].sum())} eligible")

    print("== train ==")
    models = train.load_models() if not args.retrain else {}
    retrained = set(models) != set(features.MARKETS)
    if retrained:
        models = train.train_all(frames)
    else:
        print("using cached models from", train.MODELS_DIR)

    print("== conformal calibration + thresholds (2024 split) ==")
    calib = None
    if not retrained and conformal.params_path().exists():
        try:  # cached params must include the 2024-fit thresholds (M12)
            thresholds = train.load_conf_thresholds()
            calib = conformal.load_calibrator()
            print("using cached conformal params from", conformal.params_path())
        except (ValueError, FileNotFoundError, KeyError) as err:
            print(f"cached calibration unusable ({err}); refitting")
    if calib is None:
        calib = conformal.fit_conformal(frames, models)
        thresholds = train.load_conf_thresholds()

    print("== demo week ==")
    demo_week = ex.choose_demo_week(pw, games, args.demo_week)
    print(f"demo week: 2025 week {demo_week}")

    print("== backtest ==")
    by_market = bt.run_backtest(frames, models, demo_week, calib, thresholds)
    bt.print_report(by_market)

    print("\n== export ==")
    counts = ex.run_export(pw, games, frames, models, by_market, demo_week,
                           thresholds, calib, export_dir=args.export_dir)

    print("\n== validate ==")
    rc = validate.validate(args.export_dir)
    ex.write_report(by_market, counts, demo_week, rc == 0,
                    export_dir=args.export_dir, calib=calib)
    print(f"\npipeline finished in {time.time() - t0:.0f}s "
          f"({counts['games']} games / {counts['players']} players / "
          f"{counts['props']} props); validation "
          f"{'PASSED' if rc == 0 else 'FAILED'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
