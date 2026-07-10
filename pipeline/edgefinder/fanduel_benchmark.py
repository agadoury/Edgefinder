"""M13: score the 2025 backtest against archived real FanDuel closing lines.

Evaluation ONLY — nothing here feeds features, training, calibration or the
exported JSON. The rest of the backtest measures the model against its own
refLine (a fan-expectation blend derived from features the model consumes);
this module swaps in the real market number for the two markets we have
archived FanDuel history for (pass yds, receptions) and reports honestly:

* closing line = the last archived snapshot per (event, player, market)
  taken before kickoff (the archive holds one near-closing snapshot per
  prop; the snapshot-to-kickoff gap is measured and reported),
* our projection's MAE vs the FanDuel line used as a point predictor,
* calibration of our P(over FanDuel line), read off the same calibrated
  curves the app exports,
* hit rates of our leans at FanDuel's line — overall and for strong calls
  — with Wilson 95% intervals and the break-even framing (~52.4% at -110).

Scope note: only 2025 weeks 1..demo_week-1 are scored. The archive also
covers 2023-2024, but the shipped models train through 2024 and the
calibration layers are fit ON 2024 — scoring those seasons here would not
be walk-forward, so they are deliberately left out.

Results go in the run report (and docs/BACKTEST_REPORT.md), NOT meta.json:
the app contract stays frozen. A "how the model does against real lines"
block is a candidate for a future how-it-works section.

Usage:
    python3 pipeline/edgefinder/fanduel_benchmark.py   # prints the report
"""

from __future__ import annotations

import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

if __package__ in (None, ""):  # script mode
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from edgefinder import metrics
from edgefinder.conformal import load_calibrator
from edgefinder.features import norm_name
from edgefinder.load import RAW_DIR
from edgefinder.train import (
    MODELS_DIR,
    QUANTILES,
    interp_over,
    lean_of,
    strength_of,
)

PROPS_DIR = RAW_DIR / "enrichment" / "props"
EASTERN = ZoneInfo("America/New_York")

#: FanDuel market_key -> our market id (only markets we have archives for)
MARKET_MAP = {"player_pass_yds": "pass_yds", "player_receptions": "receptions"}

PROP_FILES = {
    "pass_yds": "fanduel_pass_yds_history.csv",
    "receptions": "fanduel_receptions_history.csv",
}

#: full team names as they appear in the odds feed -> nfldata codes
TEAM_NAME_TO_CODE = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN",
    "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE",
    "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}

BREAK_EVEN_110 = 110.0 / 210.0  # 0.5238…: win prob needed at -110 juice


def closing_lines(props: pd.DataFrame) -> pd.DataFrame:
    """Last pre-kickoff snapshot per (event, player, market).

    The archive currently carries a single near-closing snapshot per prop,
    but this is written for the general case: sort by snapshot time, drop
    anything at/after commence_time, keep the last row per key.
    """
    df = props.copy()
    df["snap_ts"] = pd.to_datetime(df["requested_snapshot_time"], utc=True)
    df["commence_ts"] = pd.to_datetime(df["commence_time"], utc=True)
    df = df[df["snap_ts"] < df["commence_ts"]]
    df = df.sort_values("snap_ts", kind="stable")
    df = df.drop_duplicates(["event_id", "player", "market_key"], keep="last")
    df["hours_to_kickoff"] = (
        (df["commence_ts"] - df["snap_ts"]).dt.total_seconds() / 3600.0
    )
    return df


def map_props_to_weeks(props: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Attach (season, week) by matching each event to the schedule.

    commence_time (UTC) is converted to the US/Eastern calendar date and
    matched to games.csv on (home, away, gameday); a +/- 1 day fallback
    absorbs any timezone edge cases. Unmatched events are dropped (and
    counted by the caller via the returned frame's size).
    """
    df = props.copy()
    df["home"] = df["home_team"].map(TEAM_NAME_TO_CODE)
    df["away"] = df["away_team"].map(TEAM_NAME_TO_CODE)
    unmapped = df["home"].isna() | df["away"].isna()
    if unmapped.any():
        bad = set(df.loc[df["home"].isna(), "home_team"]) | set(
            df.loc[df["away"].isna(), "away_team"])
        raise ValueError(f"unmapped odds-feed team names: {sorted(bad)}")
    df["et_date"] = df["commence_ts"].dt.tz_convert(EASTERN).dt.date.astype(str)

    sched = games[["game_id", "season", "week", "gameday",
                   "home_team", "away_team"]].copy()
    out = df.merge(
        sched, left_on=["home", "away", "et_date"],
        right_on=["home_team", "away_team", "gameday"],
        how="left", suffixes=("", "_g"),
    )  # (home, away, gameday) is unique, so row order/count survive
    missing = out["season"].isna().to_numpy()
    for delta in (-1, 1):  # +/- 1 day fallback (timezone edge cases)
        if not missing.any():
            break
        shifted = (pd.to_datetime(out["et_date"])
                   + pd.Timedelta(days=delta)).dt.date.astype(str)
        retry = (out.loc[missing, ["home", "away"]]
                 .assign(et_date=shifted[missing])
                 .merge(sched, left_on=["home", "away", "et_date"],
                        right_on=["home_team", "away_team", "gameday"],
                        how="left"))
        for col in ("game_id", "season", "week"):
            out.loc[missing, col] = retry[col].to_numpy()
        missing = out["season"].isna().to_numpy()
    return out[out["season"].notna()].copy()


def _rebuild_curve(calib, market: str, row) -> list[dict]:
    """The exact exported calibrated curve for one backtest prediction row."""
    q = np.array([row[f"p{int(t * 100):02d}"] for t in QUANTILES], dtype=float)
    return calib.prob_curve(market, q, float(row["mean_pred"]))


def benchmark_market(
    bt: pd.DataFrame, props: pd.DataFrame, market: str, calib,
    strong_min: int = 60,
) -> dict | None:
    """Match one market's closing lines to backtest rows and score them."""
    sub = props[props["market_key"].map(MARKET_MAP.get) == market].copy()
    if sub.empty:
        return None
    sub["norm"] = sub["player"].map(norm_name)
    sub = sub[["norm", "season", "week", "line", "over_price", "under_price",
               "hours_to_kickoff"]]

    rows = bt[bt["market"] == market].copy()
    rows["norm"] = rows["name"].map(norm_name)
    m = rows.merge(sub, on=["norm", "season", "week"], how="inner")
    m = m.drop_duplicates(["norm", "season", "week"])  # one FD line per row
    if m.empty:
        return None

    y = m["y"].to_numpy(dtype=float)
    fd_line = m["line"].to_numpy(dtype=float)
    proj = m["projection"].to_numpy(dtype=float)

    p_over = np.empty(len(m))
    for i, (_, row) in enumerate(m.iterrows()):
        p_over[i] = interp_over(_rebuild_curve(calib, market, row),
                                float(row["line"]))
    went_over = (y > fd_line).astype(float)  # .5 lines: pushes impossible

    leans = np.array([lean_of(p) for p in p_over])
    strengths = np.array([
        strength_of(p, c) for p, c in zip(p_over, m["confidence"])
    ])
    decided = leans != "neutral"
    hits = np.where(leans[decided] == "over",
                    went_over[decided] == 1.0, went_over[decided] == 0.0)

    def _hit_block(mask: np.ndarray) -> dict | None:
        n = int(mask.sum())
        if n == 0:
            return None
        h = int(hits[mask].sum())
        lo, hi = metrics.wilson_interval(h, n)
        return {"n": n, "hits": h, "rate": round(h / n, 3),
                "wilson95": [round(lo, 3), round(hi, 3)]}

    # break-even implied by the actual FanDuel price on the side we lean to
    side_price = np.where(leans[decided] == "over",
                          m["over_price"].to_numpy()[decided],
                          m["under_price"].to_numpy()[decided])
    side_price = side_price.astype(float)
    valid = np.isfinite(side_price) & (side_price > 1.0)
    mean_break_even = (float(np.mean(1.0 / side_price[valid]))
                       if valid.any() else None)

    return {
        "market": market,
        "n": int(len(m)),
        "nEligible": int(len(rows)),
        "medianHoursToKickoff": round(float(m["hours_to_kickoff"].median()), 1),
        "maeModel": round(float(np.mean(np.abs(y - proj))), 2),
        "maeFdLine": round(float(np.mean(np.abs(y - fd_line))), 2),
        "brierAtFd": round(metrics.brier_score(p_over, went_over), 4),
        "calibration": metrics.calibration_buckets(p_over, went_over),
        "leans": _hit_block(np.ones(int(decided.sum()), dtype=bool)),
        "strongLeans": _hit_block(strengths[decided] >= strong_min),
        "meanBreakEvenAtPrices": (None if mean_break_even is None
                                  else round(mean_break_even, 4)),
    }


def run_benchmark(
    models_dir: Path = MODELS_DIR,
    raw_dir: Path = RAW_DIR,
    games: pd.DataFrame | None = None,
) -> dict[str, dict]:
    """Load everything and score both archived markets. {} when no props."""
    results: dict[str, dict] = {}
    props_dir = raw_dir / "enrichment" / "props"
    preds_path = models_dir / "backtest_predictions.csv"
    if not preds_path.exists():
        print("fanduel benchmark: no backtest predictions; skipped")
        return results
    if games is None:
        from edgefinder.load import load_games
        games = load_games(raw_dir)

    bt = pd.read_csv(preds_path, dtype={"player_id": str})
    if "mean_pred" not in bt.columns:
        print("fanduel benchmark: backtest_predictions.csv predates "
              "mean_pred; re-run the pipeline first")
        return results
    calib = load_calibrator(models_dir)

    for market, fname in PROP_FILES.items():
        path = props_dir / fname
        if not path.exists():
            print(f"fanduel benchmark: {fname} not cached; {market} skipped")
            continue
        props = closing_lines(pd.read_csv(path))
        props = map_props_to_weeks(props, games)
        props["season"] = props["season"].astype(int)
        props["week"] = props["week"].astype(int)
        res = benchmark_market(bt, props, market, calib)
        if res is not None:
            results[market] = res
    return results


def print_benchmark(results: dict[str, dict]) -> None:
    if not results:
        return
    print("\n=== M13: vs real FanDuel closing lines (2025 walk-forward) ===")
    for market, r in results.items():
        print(f"{market}: n={r['n']} (of {r['nEligible']} eligible rows), "
              f"median snapshot {r['medianHoursToKickoff']}h before kickoff")
        print(f"  MAE model {r['maeModel']} vs FD line-as-predictor "
              f"{r['maeFdLine']}; Brier at FD line {r['brierAtFd']}")
        if r["leans"]:
            lo, hi = r["leans"]["wilson95"]
            print(f"  leans: {r['leans']['hits']}/{r['leans']['n']} "
                  f"= {r['leans']['rate']:.3f} [95% {lo:.3f}, {hi:.3f}]")
        if r["strongLeans"]:
            lo, hi = r["strongLeans"]["wilson95"]
            print(f"  strong (>=60): {r['strongLeans']['hits']}/"
                  f"{r['strongLeans']['n']} = {r['strongLeans']['rate']:.3f} "
                  f"[95% {lo:.3f}, {hi:.3f}]")
        cells = [f"[{b['bucketMid']:.2f}] pred {b['predicted']:.2f} "
                 f"act {b['actual']:.2f} n={b['n']}"
                 for b in r["calibration"] if b["n"]]
        print("  calibration: " + " | ".join(cells))
    print(f"  (break-even at -110 is {BREAK_EVEN_110:.1%}; "
          "we are NOT claiming market edge)")


def report_lines(results: dict[str, dict]) -> list[str]:
    """Markdown block for the run report / docs/BACKTEST_REPORT.md."""
    if not results:
        return []
    lines = [
        "## Against real FanDuel closing lines (M13)",
        "",
        "Archived FanDuel prop snapshots (pass yds + receptions) matched to "
        "the 2025 walk-forward backtest by normalized player name and "
        "schedule-derived week; the FanDuel number is the last archived "
        "snapshot before kickoff. Everything else in this report grades the "
        "model against its own refLine — this section is the honest check "
        "against a real market. Evaluation only: none of it feeds the "
        "models, and it is deliberately NOT exported to meta.json (contract "
        "frozen; a candidate for a future how-it-works section).",
        "",
        "| market | n matched | model MAE | FD line MAE | Brier at FD | "
        "lean hit rate (n) | Wilson 95% | strong hit rate (n) | Wilson 95% |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for market, r in results.items():
        le, st = r["leans"], r["strongLeans"]
        le_txt = "-" if not le else f"{le['rate']:.3f} ({le['n']})"
        le_ci = "-" if not le else f"[{le['wilson95'][0]:.3f}, {le['wilson95'][1]:.3f}]"
        st_txt = "-" if not st else f"{st['rate']:.3f} ({st['n']})"
        st_ci = "-" if not st else f"[{st['wilson95'][0]:.3f}, {st['wilson95'][1]:.3f}]"
        lines.append(
            f"| {market} | {r['n']} | {r['maeModel']:.2f} | "
            f"{r['maeFdLine']:.2f} | {r['brierAtFd']:.4f} | {le_txt} | "
            f"{le_ci} | {st_txt} | {st_ci} |"
        )
    lines += ["", "P(over FanDuel line) calibration:", ""]
    for market, r in results.items():
        cells = [f"[{b['bucketMid']:.2f}] pred {b['predicted']:.2f} "
                 f"act {b['actual']:.2f} n={b['n']}"
                 for b in r["calibration"] if b["n"]]
        lines.append(f"* **{market}** — " + " | ".join(cells))
    be = [f"{r['meanBreakEvenAtPrices']:.1%} ({m})"
          for m, r in results.items() if r["meanBreakEvenAtPrices"]]
    lines += [
        "",
        f"A ~52.4% hit rate is the break-even at standard -110 pricing"
        + (f" (the archived FanDuel prices on our leaned sides imply "
           f"{' and '.join(be)})" if be else "")
        + ". The hit rates above carry wide intervals and sit near that "
        "bar — **we are NOT claiming market edge**; against real closing "
        "lines the model is a study tool, not a money machine. Snapshots "
        "are near-closing (median hours to kickoff reported per market: "
        + ", ".join(f"{m} {r['medianHoursToKickoff']}h"
                    for m, r in results.items())
        + "), not the literal final tick. 2023-2024 archive seasons are "
        "excluded because the shipped models train through 2024 — scoring "
        "them here would not be walk-forward.",
        "",
    ]
    return lines


if __name__ == "__main__":
    res = run_benchmark()
    print_benchmark(res)
    if res:
        print("\n" + "\n".join(report_lines(res)))
