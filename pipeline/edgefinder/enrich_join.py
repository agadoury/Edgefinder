"""Join the nflverse enrichment datasets onto tidy player-weeks (M9/M10).

Our player-weeks are keyed by fantasy.nfl.com PlayerId + display name +
nfldata-canonical team + season/week (load.py). The enrichment sources
(snap counts, injuries, stats_player_week) key players by name + their own
team code + season/week instead, so this module provides the crosswalk:

* Team codes are verified empirically against the schedule every load —
  all three sources currently ship nfldata-canonical codes (``LA`` for the
  Rams, all five seasons, checked 2026-07), and any code that ever drifts
  is resolved through the schedule like load.derive_team_map or raises.
* Names are matched with the same normalizer family used for QB matching
  and headshots (lowercase, accents/punctuation/suffixes stripped — see
  ``norm_join_name``), adapted from headshots.merge_name but more
  aggressive (spaces removed) so "D.J. Moore"/"DJ Moore" style drift
  can't split a player across sources.
* The join runs in two stages: exact (name, team, season, week) first,
  then a name-only (season, week) fallback restricted to keys that are
  unambiguous on BOTH sides. The fallback exists because hvpkod's
  2021-2024 archives retro-apply a player's end-of-season team to every
  week (e.g. Christian McCaffrey shows SF for his 2022 CAR weeks), while
  nflverse carries the true per-week team — team-keyed joins alone lose
  traded players' early weeks.

Coverage is measured and printed per source per season; a source must
cover > 90% of our played player-weeks (snap counts / player stats) or
match > 90% of its own fantasy-relevant rows (injuries — most of our rows
are legitimately absent from injury reports, so the direction flips) to be
trusted as a feature input. Unjoinable rows keep NaN + an explicit
missing indicator downstream — never silent zeros.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from edgefinder.features import norm_name
from edgefinder.load import RAW_DIR, SEASONS

ENRICH_DIR = RAW_DIR / "enrichment"

#: minimum acceptable join coverage for a source to feed features
MIN_COVERAGE = 0.90

#: injuries position -> our position group (others: not a skill position)
POS_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "HB": "RB",
             "WR": "WR", "TE": "TE"}

JOIN_KEY = ["norm", "team", "season", "week"]
NAME_KEY = ["norm", "season", "week"]

#: air-yards block carried from stats_player_week (plus helpers for ratios)
AIR_STAT_COLS = ["target_share", "air_yards_share", "wopr", "racr",
                 "receiving_air_yards", "passing_air_yards",
                 "receiving_yards", "targets"]


def norm_join_name(name: str) -> str:
    """Cross-source join normalizer (adapted from headshots.merge_name).

    headshots.merge_name lowercases, strips periods/apostrophes and
    suffixes but keeps spaces/hyphens (to mirror DynastyProcess's
    merge_name). For source joins we go further — accents folded and
    everything non-alphabetic dropped — because the sources disagree on
    spacing and punctuation ("Amon-Ra St. Brown" / "Amon-Ra St.Brown").
    That is exactly features.norm_name, reused so QB matching, headshots
    and enrichment joins can never drift apart silently.
    """
    return norm_name(name)


@dataclass
class JoinCoverage:
    """Per-season join coverage for one source, plus the gate result."""

    source: str
    by_season: dict[int, float]
    denominator: str
    n: int

    @property
    def ok(self) -> bool:
        return all(v > MIN_COVERAGE for v in self.by_season.values())

    def print(self) -> None:
        cells = " ".join(f"{s}={v:.3f}" for s, v in sorted(self.by_season.items()))
        verdict = "OK" if self.ok else f"BELOW {MIN_COVERAGE:.0%} — NOT USED"
        print(f"join coverage {self.source} (n={self.n}, per {self.denominator}): "
              f"{cells} -> {verdict}")


@dataclass
class Enrichment:
    """Matched enrichment tables, keyed by our player_id + season + week.

    ``snap_games`` / ``air_games`` are per-played-game observations —
    consumers MUST roll them into features via strict backward as-of joins
    (past weeks only). ``injury_weeks`` is the current week's official
    report and is the one table that may be joined exactly on the target
    week: game-status/practice designations are published before kickoff.
    ``pos_out_counts`` aggregates report_status == Out per
    (season, week, team, pos_group) for the same-week redistribution
    features. Any table may be None when its source is unavailable or
    failed the coverage gate.
    """

    snap_games: pd.DataFrame | None = None
    air_games: pd.DataFrame | None = None
    injury_weeks: pd.DataFrame | None = None
    pos_out_counts: pd.DataFrame | None = None
    coverage: dict[str, JoinCoverage] = field(default_factory=dict)


def _pw_keys(pw: pd.DataFrame) -> pd.DataFrame:
    keys = pw[["player_id", "name", "team", "season", "week"]].copy()
    keys["norm"] = keys["name"].map(norm_join_name)
    return keys


def _verify_team_codes(src: pd.DataFrame, source: str,
                       nfl_codes: set[str]) -> pd.DataFrame:
    """All source team codes must be nfldata-canonical (or resolvable).

    The three nflverse sources currently ship canonical codes for every
    season (verified empirically). If a future season drifts (e.g. LAR
    for LA), resolution mirrors load.derive_team_map: an unknown code is
    accepted only when the schedule pins it to exactly one canonical team
    via the source's own opponent column; otherwise this raises rather
    than silently mis-keying a team.
    """
    codes = set(src["team"].dropna().unique())
    unknown = codes - nfl_codes
    if not unknown:
        return src
    if "opponent" not in src.columns:
        raise ValueError(
            f"{source}: unmappable team codes {sorted(unknown)} "
            "(no opponent column to resolve them against the schedule)"
        )
    mapping: dict[str, str] = {}
    for code in sorted(unknown):
        opps = set(src.loc[src["team"] == code, "opponent"].dropna()) & nfl_codes
        # the only canonical code never seen as this team's opponent and
        # not otherwise present is the team itself
        cands = nfl_codes - opps - codes
        if len(cands) != 1:
            raise ValueError(
                f"{source}: cannot resolve team code {code!r} "
                f"(candidates: {sorted(cands)})"
            )
        mapping[code] = cands.pop()
    out = src.copy()
    out["team"] = out["team"].map(lambda c: mapping.get(c, c))
    print(f"{source}: resolved drifted team codes {mapping}")
    return out


def two_stage_join(
    pw_keys: pd.DataFrame, src: pd.DataFrame, val_cols: list[str]
) -> pd.DataFrame:
    """Attach ``val_cols`` from ``src`` to each pw_keys row (NaN = no match).

    Stage 1 joins on (normalized name, team, season, week). Stage 2
    rescues rows only where the (name, season, week) key is unambiguous
    on both sides — this recovers traded players whose hvpkod team code
    is retro-applied (see module docstring) without ever guessing between
    two same-named players.
    """
    src = src.dropna(subset=["norm", "team"])
    s1 = src.drop_duplicates(JOIN_KEY, keep="last")
    out = pw_keys.merge(s1[JOIN_KEY + val_cols], on=JOIN_KEY, how="left")
    out["join_stage"] = np.where(out[val_cols[0]].notna(), 1, 0)

    # stage 2: name-only, both sides unambiguous
    pw_amb = pw_keys.groupby(NAME_KEY)["player_id"].transform("nunique")
    src_n = src.groupby(NAME_KEY)["team"].nunique()
    s2 = (src.drop_duplicates(NAME_KEY, keep="last")
             .merge(src_n[src_n == 1].rename("_uniq").reset_index(), on=NAME_KEY))
    fb = out.merge(s2[NAME_KEY + val_cols], on=NAME_KEY, how="left",
                   suffixes=("", "_fb"))
    fill = ((out["join_stage"] == 0)
            & (pw_amb.to_numpy() == 1)
            & fb[f"{val_cols[0]}_fb"].notna().to_numpy())
    for c in val_cols:
        out.loc[fill, c] = fb.loc[fill, f"{c}_fb"].to_numpy()
    out.loc[fill, "join_stage"] = 2
    return out


def _read_seasonal(subdir: str, template: str,
                   raw_dir: Path) -> pd.DataFrame | None:
    frames = []
    for season in SEASONS:
        path = raw_dir / "enrichment" / subdir / template.format(season=season)
        if not path.exists():
            print(f"enrichment {subdir}: {path.name} missing — source skipped")
            return None
        frames.append(pd.read_csv(path, low_memory=False))
    return pd.concat(frames, ignore_index=True)


def load_snap_counts(raw_dir: Path = RAW_DIR) -> pd.DataFrame | None:
    """REG-season offensive snap rows: norm/team/season/week + offense_pct."""
    df = _read_seasonal("snap_counts", "snap_counts_{season}.csv.gz", raw_dir)
    if df is None:
        return None
    df = df[df["game_type"] == "REG"].copy()
    df["norm"] = df["player"].map(norm_join_name)
    df["offense_pct"] = pd.to_numeric(df["offense_pct"], errors="coerce")
    df["offense_snaps"] = pd.to_numeric(df["offense_snaps"], errors="coerce")
    # a duplicate (name, team, week) key keeps the busier row
    df = df.sort_values("offense_snaps", kind="stable")
    return df[["norm", "team", "season", "week", "offense_pct", "offense_snaps"]]


def load_player_stats(raw_dir: Path = RAW_DIR) -> pd.DataFrame | None:
    """REG-season stats_player_week rows with the air-yards block."""
    df = _read_seasonal("player_stats", "stats_player_week_{season}.csv", raw_dir)
    if df is None:
        return None
    df = df[df["season_type"] == "REG"].copy()
    df["norm"] = df["player_display_name"].map(norm_join_name)
    for c in AIR_STAT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df[c] = df[c].replace([np.inf, -np.inf], np.nan)
    df = df.sort_values("targets", kind="stable")
    return df[["norm", "team", "season", "week", *AIR_STAT_COLS]]


def load_injuries(raw_dir: Path = RAW_DIR) -> pd.DataFrame | None:
    """REG-season injury reports with normalized status columns.

    Handles the 2025 schema drift (extra ``season_type`` column) by
    selecting the shared columns; ``game_type`` == "REG" exists in every
    season. Junk practice_status values (a literal newline appears in the
    raw data) are treated as missing.
    """
    df = _read_seasonal("injuries", "injuries_{season}.csv.gz", raw_dir)
    if df is None:
        return None
    df = df[df["game_type"] == "REG"].copy()
    df["norm"] = df["full_name"].map(norm_join_name)
    df["pos_group"] = df["position"].map(POS_GROUP)

    status = df["report_status"].astype(str).str.strip().str.lower()
    df["inj_out"] = (status == "out").astype(float)
    df["inj_doubtful"] = (status == "doubtful").astype(float)
    df["inj_questionable"] = (status == "questionable").astype(float)

    practice = df["practice_status"].astype(str).str.strip().str.lower()
    df["practice_dnp"] = practice.str.startswith("did not").astype(float)
    df["practice_limited"] = practice.str.startswith("limited").astype(float)
    keep = ["norm", "team", "season", "week", "pos_group",
            "inj_out", "inj_doubtful", "inj_questionable",
            "practice_dnp", "practice_limited"]
    return df[keep]


def _coverage_on_pw(joined: pd.DataFrame, pw: pd.DataFrame, source: str,
                    probe_col: str) -> JoinCoverage:
    """Share of our played player-weeks that found a source row."""
    elig = (pw["played"] & pw["has_game"]).to_numpy()
    sub = joined[elig]
    by_season = {
        int(s): float(grp[probe_col].notna().mean())
        for s, grp in sub.groupby("season")
    }
    return JoinCoverage(source, by_season, "played player-weeks", int(elig.sum()))


def attach_enrichment(pw: pd.DataFrame, raw_dir: Path = RAW_DIR) -> Enrichment:
    """Load, verify, join and gate all enrichment sources against ``pw``."""
    out = Enrichment()
    keys = _pw_keys(pw)
    nfl_codes = set(pw["team"].dropna().unique())

    snaps = load_snap_counts(raw_dir)
    if snaps is not None:
        snaps = _verify_team_codes(snaps, "snap_counts", nfl_codes)
        joined = two_stage_join(keys, snaps, ["offense_pct"])
        cov = _coverage_on_pw(joined, pw, "snap_counts", "offense_pct")
        out.coverage["snap_counts"] = cov
        cov.print()
        if cov.ok:
            good = joined[joined["offense_pct"].notna()]
            out.snap_games = good[["player_id", "season", "week",
                                   "offense_pct"]].reset_index(drop=True)

    stats = load_player_stats(raw_dir)
    if stats is not None:
        stats = _verify_team_codes(stats, "player_stats", nfl_codes)
        stats = stats.assign(_hit=1.0)
        joined = two_stage_join(keys, stats, ["_hit", *AIR_STAT_COLS])
        cov = _coverage_on_pw(joined, pw, "player_stats", "_hit")
        out.coverage["player_stats"] = cov
        cov.print()
        if cov.ok:
            good = joined[joined["_hit"].notna()]
            out.air_games = good[["player_id", "season", "week",
                                  *AIR_STAT_COLS]].reset_index(drop=True)

    injuries = load_injuries(raw_dir)
    if injuries is not None:
        injuries = _verify_team_codes(injuries, "injuries", nfl_codes)
        # redistribution counts need no player join — team + week + position
        out.pos_out_counts = (
            injuries[injuries["pos_group"].notna()]
            .groupby(["season", "week", "team", "pos_group"], as_index=False)
            ["inj_out"].sum()
            .rename(columns={"inj_out": "n_out"})
        )
        status_cols = ["inj_out", "inj_doubtful", "inj_questionable",
                       "practice_dnp", "practice_limited"]
        skill = injuries[injuries["pos_group"].notna()].assign(_hit=1.0)
        joined = two_stage_join(keys, skill, ["_hit", *status_cols])
        # coverage direction flips: most of OUR rows are rightly absent
        # from the report, so we gate on how many fantasy-relevant source
        # rows found a home instead. Fantasy-relevant = the player exists
        # in our source that season (never-rostered special-teamers etc.
        # can't match anything and would only muddy the number), and the
        # (season, week) exists in our player-week universe at all
        # (hvpkod's 2024 archive stops at week 16, 2021-2023 at week 17 —
        # report rows for absent weeks have nothing to join onto).
        known = keys[["norm", "season"]].drop_duplicates().assign(_known=1.0)
        have_weeks = keys[["season", "week"]].drop_duplicates()
        probe = skill.merge(known, on=["norm", "season"], how="left")
        probe = probe[probe["_known"].notna()]
        probe = probe.merge(have_weeks, on=["season", "week"])
        matched = probe.merge(
            joined.loc[joined["_hit"].notna(),
                       ["norm", "season", "week"]].drop_duplicates(),
            on=["norm", "season", "week"], how="left", indicator=True)
        by_season = {
            int(s): float((grp["_merge"] == "both").mean())
            for s, grp in matched.groupby("season")
        }
        cov = JoinCoverage("injuries", by_season,
                           "fantasy-relevant report rows", len(probe))
        out.coverage["injuries"] = cov
        cov.print()
        if cov.ok:
            good = joined[joined["_hit"].notna()]
            out.injury_weeks = good[["player_id", "season", "week",
                                     *status_cols]].reset_index(drop=True)
        else:
            out.pos_out_counts = None
    return out
