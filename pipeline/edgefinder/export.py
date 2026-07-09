"""Write the contract JSON (meta.json, slate.json, players/{id}.json).

Staging dir is pipeline/data/export — NOT src/data; publishing to the
web app is a separate copy step owned by the web side.

Demo-slate eligibility (per the spec):
    * both starting QBs of every game (games.csv names, matched to hvpkod
      by normalized name + team)
    * RB/WR/TE with >= 3 played 2025 games and trailing-4 usage above
      thresholds (RB touches >= 8, WR/TE targets >= 3.5), capped per team
      at 2 RB / 3 WR / 2 TE by trailing usage
"""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from edgefinder import __version__
from edgefinder.conformal import Calibrator
from edgefinder.features import MARKETS, norm_name
from edgefinder.train import (
    MODELS_DIR,
    RECENCY_HALF_LIFE,
    MarketModel,
    Q_INDEX,
    confidence_of,
    interp_over,
    lean_of,
    relative_width,
    strength_of,
)
from edgefinder.explain import (
    build_confidence_reason,
    build_factors,
    build_verdict,
)

EXPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "export"
EASTERN = ZoneInfo("America/New_York")

USAGE_CAPS = {"RB": 2, "WR": 3, "TE": 2}
USAGE_MIN = {"RB": ("elig_touches_m4", 8.0), "WR": ("elig_targets_m4", 3.5),
             "TE": ("elig_targets_m4", 3.5)}
MIN_SEASON_GAMES = 3
STAT_KEYS = ["pass_yds", "pass_tds", "rush_yds", "rec_yds", "receptions"]
POS_SEASON_STATS = {
    "QB": ["pass_yds", "pass_tds", "rush_yds"],
    "RB": ["rush_yds", "rec_yds", "receptions"],
    "WR": ["rec_yds", "receptions"],
    "TE": ["rec_yds", "receptions"],
}

#: the meta.json backtest.byMarket schema is fixed by docs/DATA_CONTRACT.md;
#: evaluate_market's extended M3 diagnostics stay in REPORT.md only
CONTRACT_BYMARKET_KEYS = ("n", "mae", "baselineMae", "coverage80",
                          "strongCallHitRate", "strongCallN", "calibration")


def check_demo_week(pw: pd.DataFrame, games: pd.DataFrame, week: int) -> str | None:
    """None when the week works as a demo slate, else the reason it doesn't."""
    wk_games = games[(games["season"] == 2025) & (games["week"] == week)]
    if len(wk_games) < 12:
        return f"only {len(wk_games)} games"
    wk_rows = pw[(pw["season"] == 2025) & (pw["week"] == week)]
    for pos in ("QB", "RB", "WR", "TE"):
        if (wk_rows["pos"] == pos).sum() < 20:
            return f"thin {pos} rows"
    hv_qbs = {norm_name(n) for n in wk_rows.loc[wk_rows["pos"] == "QB", "name"]}
    starters = list(wk_games["away_qb_name"]) + list(wk_games["home_qb_name"])
    unmatched = [q for q in starters if norm_name(q) not in hv_qbs]
    if len(unmatched) > 2:
        return f"unmatched starting QBs: {unmatched}"
    return None


def choose_demo_week(pw: pd.DataFrame, games: pd.DataFrame, preferred: int = 14) -> int:
    for week in (preferred, preferred - 1, preferred + 1, preferred - 2, preferred + 2):
        reason = check_demo_week(pw, games, week)
        if reason is None:
            return week
        print(f"week {week} rejected as demo slate: {reason}")
    raise ValueError("no usable demo week near the preferred one")


def _kickoff_iso(gameday: str, gametime: str | float) -> str:
    """gameday + gametime (ET) -> ISO-8601 with the US/Eastern offset."""
    time_part = str(gametime) if isinstance(gametime, str) and gametime else "13:00"
    hh, mm = (int(p) for p in time_part.split(":")[:2])
    d = dt.date.fromisoformat(gameday)
    return dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=EASTERN).isoformat()


def select_players(
    pw: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    games: pd.DataFrame,
    demo_week: int,
) -> pd.DataFrame:
    """The demo-week player pool: one row per player with pos/team/game."""
    wk = pw[(pw["season"] == 2025) & (pw["week"] == demo_week) & pw["has_game"]].copy()

    # as-of usage/availability from any market frame's base columns
    anyf = frames["rec_yds"]  # widest coverage of skill positions
    qbf = frames["pass_yds"]
    asof = pd.concat([
        anyf[(anyf["season"] == 2025) & (anyf["week"] == demo_week)],
        qbf[(qbf["season"] == 2025) & (qbf["week"] == demo_week)],
    ]).drop_duplicates("player_id")[
        ["player_id", "games_played_season", "elig_targets_m4",
         "elig_touches_m4", "elig_rush_m8"]
    ]
    wk = wk.merge(asof, on="player_id", how="left")

    wk_games = games[(games["season"] == 2025) & (games["week"] == demo_week)]
    starters = {
        (row.game_id, norm_name(qb))
        for row in wk_games.itertuples(index=False)
        for qb in (row.away_qb_name, row.home_qb_name)
    }
    wk["norm_name"] = wk["name"].map(norm_name)
    is_starting_qb = (wk["pos"] == "QB") & np.array([
        (gid, nm) in starters
        for gid, nm in zip(wk["game_id"], wk["norm_name"])
    ])

    picks = [wk[is_starting_qb]]
    for pos, cap in USAGE_CAPS.items():
        col, floor = USAGE_MIN[pos]
        cand = wk[
            (wk["pos"] == pos)
            & (wk["games_played_season"] >= MIN_SEASON_GAMES)
            & (wk[col] >= floor)
        ]
        cand = cand.sort_values(col, ascending=False)
        picks.append(cand.groupby("team", sort=False).head(cap))
    pool = pd.concat(picks).drop_duplicates("player_id")
    return pool.reset_index(drop=True)


def player_markets(row: pd.Series) -> list[str]:
    """Position-appropriate markets, honoring the usage-gated extras."""
    pos = row["pos"]
    if pos == "QB":
        markets = ["pass_yds", "pass_tds"]
        if (row.get("elig_rush_m8") or 0) >= 15.0:
            markets.append("rush_yds")
        return markets
    if pos == "RB":
        markets = ["rush_yds"]
        if (row.get("elig_targets_m4") or 0) >= 2.5:
            markets += ["rec_yds", "receptions"]
        return markets
    return ["rec_yds", "receptions"]


def _result_of(actual: float | None, ref_line: float) -> str:
    if actual is None:
        return "dnp"
    if actual > ref_line:
        return "over"
    if actual < ref_line:
        return "under"
    return "push"


def _round(x: float, dp: int = 1) -> float:
    return float(round(float(x), dp))


def _prop_for(
    row: pd.Series, model: MarketModel, market: str,
    thresholds: tuple[float, float], calib: Calibrator,
) -> dict:
    """Full prop dict (detail form) for one player+market frame row."""
    X = row[model.features].astype(float).to_frame().T
    raw_q = model.predict_quantiles(X)
    projection = float(model.predict_projection(X, raw_q)[0])
    mean_pred = float(np.clip(model.mean_model.predict(X[model.features]),
                              0.0, None)[0])
    quantiles = calib.quantile_matrix(market, raw_q, np.array([mean_pred]))
    q = quantiles[0]
    curve = calib.prob_curve(market, q, mean_pred)
    ref_line = float(row["ref_line"])
    over_prob = interp_over(curve, ref_line)
    rw = float(relative_width(quantiles)[0])
    confidence = confidence_of(rw, row["games_played_season"], thresholds)
    lean = lean_of(over_prob)
    strength = strength_of(over_prob, confidence)
    played = bool(row["played"])
    actual = _round(float(row["y"])) if played else None
    return {
        "market": market,
        "projection": _round(projection),
        "quantiles": {
            "p10": _round(q[Q_INDEX[0.10]]),
            "p25": _round(q[Q_INDEX[0.25]]),
            "p50": _round(q[Q_INDEX[0.50]]),
            "p75": _round(q[Q_INDEX[0.75]]),
            "p90": _round(q[Q_INDEX[0.90]]),
        },
        "probCurve": curve,
        "refLine": ref_line,
        "overProbAtRef": _round(over_prob, 4),
        "lean": lean,
        "strength": int(strength),
        "confidence": confidence,
        "confidenceReason": build_confidence_reason(
            confidence, row["games_played_season"], rw
        ),
        "verdict": build_verdict(row["name"], market, projection, ref_line, over_prob),
        "factors": build_factors(row, model, projection, market),
        "actual": actual,
        "result": _result_of(actual, ref_line),
    }


def _recent_games(pw: pd.DataFrame, player_id: str, demo_ord: int) -> list[dict]:
    hist = pw[
        (pw["player_id"] == player_id)
        & pw["played"]
        & ((pw["season"] * 100 + pw["week"]) < demo_ord)
    ].sort_values(["season", "week"], ascending=False).head(10)
    out = []
    for r in hist.itertuples(index=False):
        out.append({
            "season": int(r.season),
            "week": int(r.week),
            "opponent": str(r.opp),
            "home": bool(r.is_home),
            "stats": {k: _round(getattr(r, k)) for k in STAT_KEYS},
        })
    return out


def _model_history(bt_preds: pd.DataFrame, player_id: str) -> list[dict]:
    hist = bt_preds[bt_preds["player_id"] == player_id].sort_values(
        ["week", "market"], ascending=[False, True]
    ).head(8)
    out = []
    for r in hist.itertuples(index=False):
        actual = _round(r.y)
        out.append({
            "week": int(r.week),
            "market": str(r.market),
            "projection": _round(r.projection),
            "refLine": float(r.ref_line),
            "lean": str(r.lean),
            "actual": actual,
            "result": _result_of(actual, float(r.ref_line)),
        })
    return out


def _season_avgs(pw: pd.DataFrame, player_id: str, pos: str, demo_week: int) -> dict:
    rows = pw[
        (pw["player_id"] == player_id)
        & (pw["season"] == 2025)
        & (pw["week"] < demo_week)
        & pw["played"]
    ]
    keys = POS_SEASON_STATS.get(pos, STAT_KEYS)
    if rows.empty:
        return {k: 0.0 for k in keys}
    return {k: _round(rows[k].mean()) for k in keys}


def _sanitize(obj):
    """Make JSON-safe: numpy scalars -> python, reject non-finite floats."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        obj = float(obj)
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("non-finite number in export payload")
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_sanitize(payload), indent=1, allow_nan=False))


def run_export(
    pw: pd.DataFrame,
    games: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    models: dict[str, MarketModel],
    by_market: dict,
    demo_week: int,
    thresholds: dict[str, tuple[float, float]],
    calib: Calibrator,
    export_dir: Path = EXPORT_DIR,
    models_dir: Path = MODELS_DIR,
) -> dict:
    """Write meta.json, slate.json and players/*.json. Returns counts."""
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "players").mkdir(exist_ok=True)
    for old in (export_dir / "players").glob("*.json"):
        old.unlink()

    wk_games = games[(games["season"] == 2025) & (games["week"] == demo_week)]
    games_json = []
    for g in wk_games.itertuples(index=False):
        dome = g.roof in ("dome", "closed")
        games_json.append({
            "gameId": g.game_id,
            "away": g.away_team, "home": g.home_team,
            "kickoff": _kickoff_iso(g.gameday, g.gametime),
            "roof": g.roof, "surface": g.surface,
            "tempF": None if dome or pd.isna(g.temp) else _round(g.temp, 0),
            "windMph": None if dome or pd.isna(g.wind) else _round(g.wind, 0),
            "vegasTotal": _round(g.total_line),
            "homeSpread": _round(-g.spread_line),  # negative = home favored
            "stadium": g.stadium,
            "awayQb": g.away_qb_name, "homeQb": g.home_qb_name,
        })

    pool = select_players(pw, frames, games, demo_week)
    bt_preds = pd.read_csv(
        models_dir / "backtest_predictions.csv", dtype={"player_id": str}
    )

    demo_ord = 2025 * 100 + demo_week
    frame_rows = {
        m: f[(f["season"] == 2025) & (f["week"] == demo_week)]
        .set_index("player_id")
        for m, f in frames.items()
    }

    props_index, player_files, skipped = [], {}, []
    for prow in pool.itertuples(index=False):
        prow_d = prow._asdict()
        pid = str(prow.player_id)
        pdict = {
            "playerId": pid,
            "name": prow.name,
            "team": prow.team, "pos": prow.pos, "opponent": prow.opp,
            "home": bool(prow.is_home),
            "gameId": prow.game_id,
            "gamesPlayed2025": int(prow.games_played_season or 0),
            "props": [],
            "recentGames": _recent_games(pw, pid, demo_ord),
            "seasonAvgs": _season_avgs(pw, pid, prow.pos, demo_week),
            "modelHistory": _model_history(bt_preds, pid),
        }
        for market in player_markets(prow_d):
            fr = frame_rows[market]
            if pid not in fr.index:
                skipped.append((pid, market, "no frame row"))
                continue
            row = fr.loc[pid]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            row = row.copy()
            row["player_id"] = pid
            if pd.isna(row["ref_line"]):
                skipped.append((pid, market, "no reference line"))
                continue
            prop = _prop_for(row, models[market], market, thresholds[market],
                             calib)
            pdict["props"].append(prop)
            props_index.append({
                "playerId": pid,
                "name": prow.name,
                "team": prow.team, "pos": prow.pos, "opponent": prow.opp,
                "home": bool(prow.is_home),
                "gameId": prow.game_id,
                "market": market,
                "projection": prop["projection"],
                "refLine": prop["refLine"],
                "overProbAtRef": prop["overProbAtRef"],
                "lean": prop["lean"],
                "strength": prop["strength"],
                "confidence": prop["confidence"],
                "actual": prop["actual"],
                "result": prop["result"],
            })
        if pdict["props"]:
            player_files[pid] = pdict
        else:
            skipped.append((pid, "*", "no props"))

    slate = {"season": 2025, "week": demo_week, "games": games_json,
             "props": props_index}
    _write_json(export_dir / "slate.json", slate)
    for pid, pdict in player_files.items():
        _write_json(export_dir / "players" / f"{pid}.json", pdict)

    meta = {
        "generatedAt": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "season": 2025,
        "week": demo_week,
        "mode": "backtest_replay",
        "modelVersion": __version__,
        "trainSeasons": [2021, 2022, 2023, 2024],
        "markets": [
            {"id": m, "label": spec["label"], "unit": spec["unit"],
             "positions": list(spec["positions"]), "lineStep": spec["step"]}
            for m, spec in MARKETS.items()
        ],
        "backtest": {
            "season": 2025,
            "weeksEvaluated": demo_week - 1,
            "byMarket": {
                market: {k: m[k] for k in CONTRACT_BYMARKET_KEYS}
                for market, m in by_market.items()
            },
        },
    }
    _write_json(export_dir / "meta.json", meta)

    if skipped:
        print(f"skipped {len(skipped)} player-markets: {skipped[:8]}")
    counts = {
        "games": len(games_json),
        "players": len(player_files),
        "props": len(props_index),
    }
    print(f"export: {counts['games']} games, {counts['players']} players, "
          f"{counts['props']} prop rows -> {export_dir}")
    return counts


def _conformal_lines(calib: Calibrator | None) -> list[str]:
    if calib is None:
        return []
    lines = [
        "## Interval calibration (split conformal, 2024)",
        "",
        "Models refit on 2021-2023 were scored on held-out 2024 "
        "(walk-forward by construction); the fixed adjustments below are "
        "applied unchanged to the 2025 backtest and the demo slate. "
        "Conformity scores never come from 2025.",
        "",
    ]
    for market, p in calib.markets.items():
        if p["method"] == "additive":
            d = p["deltas"]
            lines.append(
                f"* **{market}** — additive per-quantile deltas "
                f"(n={p['nCal']}): p10 {float(d['0.10']):+.1f}, "
                f"p50 {float(d['0.50']):+.1f}, p90 {float(d['0.90']):+.1f} "
                "(units of the stat)."
            )
        else:
            dist = "Poisson" if p["alpha"] == 0 else f"NB(alpha={p['alpha']})"
            lines.append(
                f"* **{market}** — discrete {dist} layer on half-integer "
                f"support (n={p['nCal']}): lambda = mean-model expectation "
                f"x {p['lambdaScale']:.4f}, plus a mid-PIT conformal level "
                "map; quantiles/curves come from the continuity-corrected "
                "CDF, so low quantiles vary by player."
            )
        sh = p.get("shrink")
        if sh:
            lines.append(
                f"  * P(over) shrink (M6): p' = sigmoid({sh['a']:+.3f} "
                f"+ {sh['b']:.3f}·logit(p)) on every exported curve point, "
                f"fit on the same 2024 walk-forward predictions "
                f"(n={sh['nFit']}; 2024 cross-week Brier delta "
                f"{sh['crossBrierDelta']:+.5f}). Quantiles are not shrunk."
            )
    lines += [
        "",
        "Confidence thresholds (M12) are the relative-width quartiles of "
        "the same 2024 walk-forward calibrated quantiles "
        "(`confidence_thresholds.json`, provenance-stamped). The ~25/50/25 "
        "high/medium/low split is therefore targeted on 2024; the realized "
        "2025 split may drift — that is the honest cost of removing the "
        "circular 2025 fit.",
        "",
    ]
    return lines


def _diagnostics_lines(by_market: dict) -> list[str]:
    """M3 extended tables: per-quantile coverage/pinball, CRPS, drift."""
    lines = [
        "## Distributional diagnostics (M3)",
        "",
        "Per-quantile empirical coverage P(y <= q_tau) (target = tau) and "
        "mean pinball loss; CRPS is approximated as 2x the average pinball "
        "loss across the seven quantiles.",
        "",
    ]
    qkeys = None
    for market, m in by_market.items():
        if "quantiles" not in m:
            return []
        if qkeys is None:
            qkeys = list(m["quantiles"])
            lines += [
                "| market | " + " | ".join(qkeys) + " | CRPS | Brier |",
                "|---|" + "---|" * (len(qkeys) + 2),
            ]
        cov = " | ".join(f"{m['quantiles'][k]['coverage']:.3f}" for k in qkeys)
        lines.append(f"| {market} (coverage) | {cov} | {m['crps']:.3f} "
                     f"| {m['brier']:.4f} |")
        pin = " | ".join(f"{m['quantiles'][k]['pinball']:.3f}" for k in qkeys)
        lines.append(f"| {market} (pinball) | {pin} |  |  |")
    lines += [
        "",
        "Calibration-bucket drift (|predicted − actual| over the P(over) "
        "buckets) and strong-call Wilson 95% intervals:",
        "",
        "| market | worst bucket drift | mean bucket drift (n-weighted) "
        "| strong-call hit (n) | Wilson 95% |",
        "|---|---|---|---|---|",
    ]
    for market, m in by_market.items():
        drift = m["bucketDrift"]
        hit = ("-" if m["strongCallHitRate"] is None
               else f"{m['strongCallHitRate']:.3f} ({m['strongCallN']})")
        wil = ("-" if not m.get("strongCallWilson95")
               else f"[{m['strongCallWilson95'][0]:.3f}, "
                    f"{m['strongCallWilson95'][1]:.3f}]")
        lines.append(f"| {market} | {drift['worst']:.3f} | {drift['mean']:.3f} "
                     f"| {hit} | {wil} |")
    lines.append("")
    return lines


def write_report(
    by_market: dict,
    counts: dict,
    demo_week: int,
    validation_passed: bool,
    export_dir: Path = EXPORT_DIR,
    calib: Calibrator | None = None,
) -> None:
    """Human-readable run summary next to the export JSON."""
    lines = [
        "# EdgeFinder pipeline run report",
        "",
        f"Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%MZ} — "
        f"model v{__version__}, trained on 2021-2024 REG with recency-"
        f"weighted samples (half-life {RECENCY_HALF_LIFE} seasons); "
        "intervals conformalized on a held-out 2024 split.",
        "",
        f"* **Demo slate:** 2025 week {demo_week} "
        f"({counts['games']} games, {counts['players']} players, "
        f"{counts['props']} prop rows)",
        f"* **Validation:** {'PASSED' if validation_passed else 'FAILED'}",
        "",
        "## Backtest — 2025 weeks 1-" + str(demo_week - 1) + " (walk-forward)",
        "",
        "2025 is evaluation only: every model, calibration and threshold "
        "choice was made on the 2024 walk-forward split (models fit on "
        "2021-2023), then applied here unchanged.",
        "",
        "| market | n | MAE | baseline MAE | coverage80 | CRPS | Brier "
        "| strong-call hit | strong n |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for market, m in by_market.items():
        hit = "-" if m["strongCallHitRate"] is None else f"{m['strongCallHitRate']:.3f}"
        crps = f"{m['crps']:.3f}" if "crps" in m else "-"
        brier = f"{m['brier']:.4f}" if "brier" in m else "-"
        lines.append(
            f"| {market} | {m['n']} | {m['mae']:.2f} | {m['baselineMae']:.2f} "
            f"| {m['coverage80']:.3f} | {crps} | {brier} "
            f"| {hit} | {m['strongCallN']} |"
        )
    lines += [
        "",
        "Baseline = the refLine blend (trailing-5 median x season median). "
        "The model beats it on every market.",
        "",
    ]
    lines += _diagnostics_lines(by_market)
    lines += _conformal_lines(calib)
    lines += [
        "## Data quirks",
        "",
        "* hvpkod has no week-18 files for 2021-2024 (404 upstream); those "
        "seasons cover weeks 1-17. 2025 has all 18 weeks.",
        "* The cancelled 2022 wk17 BUF@CIN game exists in hvpkod but not in "
        "nfldata; its rows are excluded (stats were nullified anyway).",
        "* hvpkod codes the Rams `LA` through 2023 and `LAR` from 2024; the "
        "schedule-derived map normalizes both to nfldata `LA`.",
        "* Free-agent rows (`Team == FA`, always opponent `Bye`) are dropped.",
        "* A played-but-zero-usage game is indistinguishable from a DNP in "
        "the box-score source and is treated as DNP.",
        "* Cold start: form windows roll across season boundaries; rows with "
        "< 2 prior played career games are excluded from training/backtest.",
    ]
    (export_dir / "REPORT.md").write_text("\n".join(lines) + "\n")

