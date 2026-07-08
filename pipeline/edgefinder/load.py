"""Load raw CSVs into tidy, joinable DataFrames.

Outputs:
    load_games()        -- REG-season games 2021-2025 with verified spread sign
    team_game_long()    -- one row per (game, team) with team-perspective context
    load_player_weeks() -- one row per (player, season, week) with normalized
                           team codes, a `played` flag, and joined game context

Team codes are normalized to canonical nfldata codes (``LA`` for the Rams,
``WAS``, ``JAX``, ``LV``, ...). The hvpkod -> nfldata mapping is derived
empirically from the schedule: an unknown hvpkod code is resolved by finding
the nfldata game its (already-mapped) opponent played that week.
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
SEASONS = tuple(range(2021, 2026))
POSITIONS = ("QB", "RB", "WR", "TE")

#: hvpkod column -> canonical stat name (market ids where applicable)
STAT_COLUMNS: dict[str, str] = {
    "PassingYDS": "pass_yds",
    "PassingTD": "pass_tds",
    "PassingInt": "pass_ints",
    "RushingYDS": "rush_yds",
    "RushingTD": "rush_tds",
    "ReceivingRec": "receptions",
    "ReceivingYDS": "rec_yds",
    "ReceivingTD": "rec_tds",
    "TouchCarries": "carries",
    "Touches": "touches",
    "Targets": "targets",
    "TotalPoints": "fantasy_points",
}

GAME_COLUMNS = [
    "game_id", "season", "week", "gameday", "gametime",
    "away_team", "home_team", "away_score", "home_score",
    "away_rest", "home_rest", "spread_line", "total_line",
    "roof", "surface", "temp", "wind",
    "away_qb_name", "home_qb_name", "stadium",
]


def load_games(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Regular-season games for SEASONS with types coerced and spread verified.

    ``spread_line`` is the Vegas expected HOME margin (positive = home
    favored). This convention is asserted empirically each load: the
    correlation between ``spread_line`` and the actual home margin must be
    clearly positive.
    """
    games = pd.read_csv(raw_dir / "games.csv", low_memory=False)
    games = games[
        (games["game_type"] == "REG")
        & games["season"].isin(SEASONS)
    ].copy()
    played = games.dropna(subset=["home_score", "away_score", "spread_line"])
    margin = played["home_score"] - played["away_score"]
    corr = float(margin.corr(played["spread_line"]))
    if not corr > 0.2:  # pragma: no cover - data sanity guard
        raise ValueError(
            f"spread_line sign convention check failed (corr={corr:.3f}); "
            "expected positive = home favored"
        )
    for col in ("away_score", "home_score", "away_rest", "home_rest",
                "spread_line", "total_line", "temp", "wind"):
        games[col] = pd.to_numeric(games[col], errors="coerce")
    games["week"] = games["week"].astype(int)
    return games[GAME_COLUMNS].reset_index(drop=True)


def team_game_long(games: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team): team-perspective schedule and context.

    ``expected_margin`` is how many points Vegas expects THIS team to win by
    (negative = underdog). ``team_spread`` is the bookmaker-style line for the
    team (negative = favored).
    """
    def _side(home: bool) -> pd.DataFrame:
        us, them = ("home", "away") if home else ("away", "home")
        out = pd.DataFrame({
            "game_id": games["game_id"],
            "season": games["season"],
            "week": games["week"],
            "gameday": games["gameday"],
            "team": games[f"{us}_team"],
            "opp": games[f"{them}_team"],
            "is_home": home,
            "team_score": games[f"{us}_score"],
            "opp_score": games[f"{them}_score"],
            "rest_days": games[f"{us}_rest"],
            "opp_rest_days": games[f"{them}_rest"],
            "total_line": games["total_line"],
            "roof": games["roof"],
            "temp": games["temp"],
            "wind": games["wind"],
            "qb_name": games[f"{us}_qb_name"],
        })
        sign = 1.0 if home else -1.0
        out["expected_margin"] = sign * games["spread_line"].to_numpy()
        return out

    tg = pd.concat([_side(True), _side(False)], ignore_index=True)
    tg["team_spread"] = -tg["expected_margin"]
    tg["implied_pts"] = tg["total_line"] / 2 + tg["expected_margin"] / 2
    return tg.sort_values(["season", "week", "game_id", "team"]).reset_index(drop=True)


def derive_team_map(hv: pd.DataFrame, games: pd.DataFrame) -> dict[str, str]:
    """Empirically map hvpkod team codes to nfldata codes via the schedule.

    Codes shared by both sources start as identity. Each remaining hvpkod
    code is resolved by looking at weeks where its opponent is already
    mapped: the nfldata game featuring that opponent names the missing team.
    Raises if any code stays unresolved, the map is not injective, or any
    mapped (team, opp) pair contradicts the schedule.
    """
    nfl_codes = set(games["home_team"]) | set(games["away_team"])
    hv_rows = hv.loc[
        hv["PlayerOpponent"].notna()
        & (hv["PlayerOpponent"] != "Bye")
        & (hv["Team"] != "FA"),
        ["season", "wk", "Team", "PlayerOpponent"],
    ].copy()
    hv_rows["opp_raw"] = hv_rows["PlayerOpponent"].str.lstrip("@")
    hv_rows = hv_rows.drop_duplicates(["season", "wk", "Team", "opp_raw"])

    # (season, week) -> set of frozenset team pairs
    pairs: dict[tuple[int, int], list[tuple[str, str]]] = {}
    for row in games.itertuples(index=False):
        pairs.setdefault((row.season, row.week), []).append(
            (row.home_team, row.away_team)
        )

    hv_codes = set(hv_rows["Team"]) | set(hv_rows["opp_raw"])
    mapping = {code: code for code in hv_codes & nfl_codes}
    unknown = hv_codes - nfl_codes
    for _ in range(4):  # a couple of passes resolves chains
        if not unknown:
            break
        for code in sorted(unknown):
            cands: set[str] = set()
            sub = hv_rows[(hv_rows["Team"] == code)
                          & hv_rows["opp_raw"].isin(mapping)]
            for row in sub.itertuples(index=False):
                opp = mapping[row.opp_raw]
                for home, away in pairs.get((row.season, row.wk), []):
                    if home == opp:
                        cands.add(away)
                    elif away == opp:
                        cands.add(home)
            if len(cands) == 1:
                mapping[code] = cands.pop()
        unknown = {c for c in unknown if c not in mapping}
    if unknown:
        raise ValueError(f"unresolved hvpkod team codes: {sorted(unknown)}")

    # Injectivity per season: two hvpkod codes may share a target only if
    # they never coexist in a season (e.g. LA in 2021-23, LAR in 2024-25).
    for season, grp in hv_rows.groupby("season"):
        codes = set(grp["Team"]) | set(grp["opp_raw"])
        targets = [mapping[c] for c in codes]
        if len(targets) != len(set(targets)):
            raise ValueError(f"team map not injective within season {season}")

    # Every mapped (team, opp, week) must match a scheduled game -- except
    # games nfldata dropped entirely (e.g. the cancelled 2022 wk17 BUF@CIN):
    # those are tolerated when the team appears nowhere that week.
    bad = 0
    for row in hv_rows.itertuples(index=False):
        t, o = mapping[row.Team], mapping[row.opp_raw]
        week_pairs = pairs.get((row.season, row.wk), [])
        if any({t, o} == {h, a} for h, a in week_pairs):
            continue
        if any(t in p for p in week_pairs):  # plays someone else => bad map
            bad += 1
    if bad:
        raise ValueError(f"{bad} hvpkod team-weeks contradict the schedule")
    return mapping


def _read_hvpkod(raw_dir: Path) -> pd.DataFrame:
    """Concatenate every cached hvpkod weekly CSV (season/week from path)."""
    frames = []
    for path in sorted(glob.glob(str(raw_dir / "hvpkod" / "*" / "*" / "*.csv"))):
        parts = Path(path).parts
        season, week = int(parts[-3]), int(parts[-2])
        df = pd.read_csv(path, dtype=str)
        df["season"] = season
        df["wk"] = week
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"no hvpkod CSVs under {raw_dir}")
    return pd.concat(frames, ignore_index=True)


def load_player_weeks(
    raw_dir: Path = RAW_DIR, games: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Tidy player-week frame with normalized teams and joined game context.

    A row counts as ``played`` when any of touches, targets, pass_yds,
    rush_yds or receptions parses > 0, or fantasy points are nonzero.
    (A true played-but-zero-touch game is indistinguishable from a DNP and
    is treated as DNP.) Free-agent rows are dropped; bye/unscheduled rows
    are kept with ``has_game = False`` for availability features.
    """
    if games is None:
        games = load_games(raw_dir)
    hv = _read_hvpkod(raw_dir)
    hv = hv[hv["Team"] != "FA"].copy()

    team_map = derive_team_map(hv, games)

    pw = pd.DataFrame({
        "season": hv["season"].astype(int),
        "week": hv["wk"].astype(int),
        "player_id": hv["PlayerId"].astype(str),
        "name": hv["PlayerName"].astype(str),
        "pos": hv["Pos"].astype(str),
        "team": hv["Team"].map(team_map),
    })
    opp_raw = hv["PlayerOpponent"].fillna("Bye")
    on_bye = opp_raw == "Bye"
    pw["opp"] = opp_raw.str.lstrip("@").map(team_map).where(~on_bye)
    pw["is_home"] = (~opp_raw.str.startswith("@")).where(~on_bye)

    for src, dst in STAT_COLUMNS.items():
        vals = hv[src].astype(str).str.replace(",", "", regex=False)
        pw[dst] = pd.to_numeric(vals, errors="coerce").fillna(0.0)

    pw["played"] = (
        (pw[["touches", "targets", "pass_yds", "rush_yds", "receptions"]] > 0)
        .any(axis=1)
        | (pw["fantasy_points"] != 0)
    )

    dupes = pw.duplicated(["player_id", "season", "week"], keep=False)
    if dupes.any():  # defensive: none observed in the raw data
        pw = (
            pw.sort_values("fantasy_points", ascending=False)
            .drop_duplicates(["player_id", "season", "week"])
        )

    tg = team_game_long(games)
    ctx_cols = ["season", "week", "team", "game_id", "opp", "is_home",
                "team_score", "opp_score", "rest_days", "opp_rest_days",
                "total_line", "expected_margin", "team_spread", "implied_pts",
                "roof", "temp", "wind", "qb_name"]
    pw = pw.merge(
        tg[ctx_cols], on=["season", "week", "team"],
        how="left", suffixes=("_hv", ""),
    )
    pw["has_game"] = pw["game_id"].notna()

    # hvpkod opponent must agree with the schedule wherever both exist.
    both = pw["opp_hv"].notna() & pw["opp"].notna()
    mismatch = int((pw.loc[both, "opp_hv"] != pw.loc[both, "opp"]).sum())
    if mismatch:
        raise ValueError(f"{mismatch} player rows disagree with the schedule")
    pw = pw.drop(columns=["opp_hv", "is_home_hv"])
    pw.loc[~pw["has_game"], "played"] = False

    return pw.sort_values(["season", "week", "team", "player_id"]).reset_index(drop=True)
