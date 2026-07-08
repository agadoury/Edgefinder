"""Validate an export directory against every contract invariant.

Usage: python3 pipeline/edgefinder/validate.py [EXPORT_DIR]

Exits nonzero when any check fails. Checks (from docs/DATA_CONTRACT.md):
 1. every props[].playerId has a players/{id}.json
 2. every prop's gameId exists in slate games
 3. quantiles non-decreasing p10 <= p25 <= p50 <= p75 <= p90
 4. probCurve.over non-increasing as line increases
 5. overProbAtRef == interp(probCurve, refLine) +/- 0.01
 6. every prop has 1-6 factors from the fixed group list
 7. all numbers finite (the parser rejects NaN/Infinity tokens)
 8. result consistent with actual vs refLine (or dnp when actual null)
 9. (leakage is enforced by construction; spot-checked in pipeline/tests)
plus enum/type checks, canonical team codes, and slate<->player consistency.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

VALID_GROUPS = {"recent_form", "usage_role", "opp_defense", "game_environment",
                "weather", "rest_schedule", "qb_situation", "home_away"}
VALID_TEAMS = {"ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL",
               "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC", "LA", "LAC",
               "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT",
               "SEA", "SF", "TB", "TEN", "WAS"}
VALID_MARKETS = {"pass_yds", "pass_tds", "rush_yds", "rec_yds", "receptions"}
VALID_LEANS = {"over", "under", "neutral"}
VALID_CONF = {"high", "medium", "low"}
VALID_ROOFS = {"outdoors", "dome", "closed", "open"}
MARKET_STEPS = {"pass_yds": 2.5, "pass_tds": 0.5, "rush_yds": 2.5,
                "rec_yds": 2.5, "receptions": 0.5}


class Checker:
    """Collects named pass/fail results."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passed = 0

    def check(self, ok: bool, msg: str) -> None:
        if ok:
            self.passed += 1
        else:
            self.failures.append(msg)


def _reject_bad_const(value: str):  # json parse_constant hook
    raise ValueError(f"non-finite JSON constant: {value}")


def _load(path: Path):
    return json.loads(path.read_text(), parse_constant=_reject_bad_const)


def _finite_numbers(obj, path: str, ck: Checker) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _finite_numbers(v, f"{path}.{k}", ck)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _finite_numbers(v, f"{path}[{i}]", ck)
    elif isinstance(obj, float):
        ck.check(math.isfinite(obj), f"non-finite number at {path}")


def _interp(curve: list[dict], line: float) -> float:
    pts = [(p["line"], p["over"]) for p in curve]
    if line <= pts[0][0]:
        return pts[0][1]
    if line >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= line <= x1:
            if x1 == x0:
                return y0
            return y0 + (y1 - y0) * (line - x0) / (x1 - x0)
    return pts[-1][1]


def _check_prop(prop: dict, where: str, ck: Checker) -> None:
    ck.check(prop.get("market") in VALID_MARKETS, f"{where}: bad market")
    q = prop.get("quantiles", {})
    keys = ["p10", "p25", "p50", "p75", "p90"]
    ck.check(all(k in q for k in keys), f"{where}: missing quantile keys")
    vals = [q.get(k) for k in keys if q.get(k) is not None]
    ck.check(all(a <= b for a, b in zip(vals, vals[1:])),
             f"{where}: quantiles not non-decreasing")

    curve = prop.get("probCurve", [])
    ck.check(len(curve) >= 2, f"{where}: probCurve too short")
    lines = [p["line"] for p in curve]
    overs = [p["over"] for p in curve]
    ck.check(all(a < b for a, b in zip(lines, lines[1:])),
             f"{where}: probCurve lines not ascending")
    ck.check(all(a >= b for a, b in zip(overs, overs[1:])),
             f"{where}: probCurve.over increases")
    ck.check(all(0.0 <= o <= 1.0 for o in overs),
             f"{where}: probCurve.over out of [0,1]")

    ref, opr = prop.get("refLine"), prop.get("overProbAtRef")
    ck.check(isinstance(ref, (int, float)), f"{where}: refLine missing")
    ck.check(isinstance(opr, (int, float)) and 0.0 <= opr <= 1.0,
             f"{where}: overProbAtRef invalid")
    if isinstance(ref, (int, float)) and curve:
        ck.check(abs(_interp(curve, ref) - opr) <= 0.01,
                 f"{where}: overProbAtRef {opr} != curve interp "
                 f"{_interp(curve, ref):.4f} at {ref}")

    ck.check(prop.get("lean") in VALID_LEANS, f"{where}: bad lean")
    s = prop.get("strength")
    ck.check(isinstance(s, int) and 0 <= s <= 100, f"{where}: bad strength")
    ck.check(prop.get("confidence") in VALID_CONF, f"{where}: bad confidence")

    factors = prop.get("factors", [])
    ck.check(1 <= len(factors) <= 6, f"{where}: {len(factors)} factors")
    for i, f in enumerate(factors):
        ck.check(f.get("group") in VALID_GROUPS,
                 f"{where}: factor[{i}] bad group {f.get('group')}")
        ck.check(f.get("direction") in {"up", "down"},
                 f"{where}: factor[{i}] bad direction")
        ck.check(isinstance(f.get("label"), str) and f["label"],
                 f"{where}: factor[{i}] empty label")
        ck.check(isinstance(f.get("detail"), str) and f["detail"],
                 f"{where}: factor[{i}] empty detail")

    _check_result(prop.get("actual"), prop.get("result"), ref, where, ck)


def _check_result(actual, result, ref, where: str, ck: Checker) -> None:
    if actual is None:
        ck.check(result == "dnp", f"{where}: null actual but result={result}")
        return
    if not isinstance(ref, (int, float)):
        return
    expected = "over" if actual > ref else ("under" if actual < ref else "push")
    ck.check(result == expected,
             f"{where}: result {result} != {expected} (actual {actual} vs {ref})")


def validate(export_dir: Path) -> int:
    ck = Checker()
    meta_p, slate_p = export_dir / "meta.json", export_dir / "slate.json"
    for p in (meta_p, slate_p):
        if not p.exists():
            print(f"FATAL: missing {p}")
            return 1
    try:
        meta, slate = _load(meta_p), _load(slate_p)
    except ValueError as err:
        print(f"FATAL: {err}")
        return 1

    # --- meta ---------------------------------------------------------
    for key in ("generatedAt", "season", "week", "mode", "modelVersion",
                "trainSeasons", "markets", "backtest"):
        ck.check(key in meta, f"meta.json missing {key}")
    demo_week = meta.get("week")
    meta_markets = {m["id"]: m for m in meta.get("markets", [])}
    ck.check(set(meta_markets) == VALID_MARKETS,
             f"meta.markets ids {sorted(meta_markets)} != contract")
    for mid, m in meta_markets.items():
        ck.check(m.get("lineStep") == MARKET_STEPS[mid],
                 f"meta market {mid} lineStep {m.get('lineStep')}")
    bt = meta.get("backtest", {})
    ck.check(bt.get("season") == 2025, "backtest.season != 2025")
    ck.check(bt.get("weeksEvaluated") == (demo_week or 0) - 1,
             "backtest.weeksEvaluated != week-1")
    for mid, mm in bt.get("byMarket", {}).items():
        for k in ("n", "mae", "baselineMae", "coverage80", "strongCallHitRate",
                  "strongCallN", "calibration"):
            ck.check(k in mm, f"backtest {mid} missing {k}")
    _finite_numbers(meta, "meta", ck)

    # --- slate ---------------------------------------------------------
    games = slate.get("games", [])
    props = slate.get("props", [])
    ck.check(len(games) >= 12, f"only {len(games)} games in slate")
    game_ids = set()
    for g in games:
        game_ids.add(g.get("gameId"))
        ck.check(g.get("away") in VALID_TEAMS and g.get("home") in VALID_TEAMS,
                 f"game {g.get('gameId')}: non-canonical team codes")
        ck.check(g.get("roof") in VALID_ROOFS, f"game {g.get('gameId')}: roof")
        ck.check(isinstance(g.get("vegasTotal"), (int, float)),
                 f"game {g.get('gameId')}: vegasTotal")
        ck.check(isinstance(g.get("homeSpread"), (int, float)),
                 f"game {g.get('gameId')}: homeSpread")
        ck.check(isinstance(g.get("kickoff"), str) and "T" in g["kickoff"],
                 f"game {g.get('gameId')}: kickoff format")
    _finite_numbers(slate, "slate", ck)

    players_dir = export_dir / "players"
    player_json: dict[str, dict] = {}
    for prop in props:
        pid = prop.get("playerId")
        where = f"slate prop {pid}/{prop.get('market')}"
        ck.check(prop.get("gameId") in game_ids, f"{where}: unknown gameId")
        ck.check(prop.get("team") in VALID_TEAMS
                 and prop.get("opponent") in VALID_TEAMS,
                 f"{where}: non-canonical team codes")
        ck.check(prop.get("lean") in VALID_LEANS, f"{where}: bad lean")
        ck.check(prop.get("confidence") in VALID_CONF, f"{where}: bad confidence")
        s = prop.get("strength")
        ck.check(isinstance(s, int) and 0 <= s <= 100, f"{where}: bad strength")
        _check_result(prop.get("actual"), prop.get("result"),
                      prop.get("refLine"), where, ck)
        path = players_dir / f"{pid}.json"
        ck.check(path.exists(), f"{where}: missing players/{pid}.json")
        if pid not in player_json and path.exists():
            try:
                player_json[pid] = _load(path)
            except ValueError as err:
                ck.check(False, f"players/{pid}.json: {err}")

    # --- player files ------------------------------------------------------
    for pid, pj in player_json.items():
        where = f"players/{pid}.json"
        ck.check(pj.get("playerId") == pid, f"{where}: playerId mismatch")
        ck.check(pj.get("gameId") in game_ids, f"{where}: unknown gameId")
        ck.check(pj.get("team") in VALID_TEAMS
                 and pj.get("opponent") in VALID_TEAMS,
                 f"{where}: non-canonical team codes")
        _finite_numbers(pj, where, ck)
        markets_seen = set()
        for prop in pj.get("props", []):
            markets_seen.add(prop.get("market"))
            _check_prop(prop, f"{where} {prop.get('market')}", ck)
        for h in pj.get("modelHistory", []):
            ck.check(h.get("week", 99) < (demo_week or 0),
                     f"{where}: modelHistory week >= demo week")
            _check_result(h.get("actual"), h.get("result"),
                          h.get("refLine"), f"{where} history", ck)
        rg = pj.get("recentGames", [])
        ords = [g["season"] * 100 + g["week"] for g in rg]
        ck.check(ords == sorted(ords, reverse=True),
                 f"{where}: recentGames not newest-first")
        ck.check(len(rg) <= 10, f"{where}: >10 recentGames")
        ck.check(len(pj.get("modelHistory", [])) <= 8,
                 f"{where}: >8 modelHistory rows")

        # slate rows must mirror the player file numbers
        for prop in props:
            if prop.get("playerId") != pid:
                continue
            match = [p for p in pj.get("props", [])
                     if p.get("market") == prop.get("market")]
            ck.check(len(match) == 1,
                     f"{where}: slate market {prop.get('market')} not in file")
            if match:
                for k in ("projection", "refLine", "overProbAtRef", "lean",
                          "strength", "confidence", "actual", "result"):
                    ck.check(match[0].get(k) == prop.get(k),
                             f"{where}: slate/{k} mismatch for "
                             f"{prop.get('market')}")

    referenced = {p.get("playerId") for p in props}
    orphans = [p.stem for p in players_dir.glob("*.json")
               if p.stem not in referenced]
    if orphans:
        print(f"note: {len(orphans)} player files not referenced by slate props")

    print(f"\nvalidate: {ck.passed} checks passed, {len(ck.failures)} failed")
    for f in ck.failures[:40]:
        print(f"  FAIL: {f}")
    if len(ck.failures) > 40:
        print(f"  ... and {len(ck.failures) - 40} more")
    return 1 if ck.failures else 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent.parent / "data" / "export"
    )
    sys.exit(validate(target))
