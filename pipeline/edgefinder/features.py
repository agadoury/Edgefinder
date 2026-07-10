"""Leak-free feature matrices, one per market.

Every feature is computed ONLY from strictly earlier weeks. The mechanism:
feature values are stored on "event" rows (a player's played game, a team's
game, a defense's game) *including* that event, then joined onto target rows
with a backward as-of merge that forbids exact matches — so a row at week W
only ever sees events at week < W.

Cold-start policy (documented, consistent): player-form and usage windows
roll across season boundaries (previous-season games count toward "last N
played"), season-to-date columns reset each season, and rows with fewer
than 2 prior played career games are dropped from training and backtest.
"""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.IGNORECASE)


def norm_name(name: str) -> str:
    """Lowercase, strip accents/punctuation/suffixes — for QB name matching."""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _SUFFIXES.sub("", s.lower())
    return re.sub(r"[^a-z]", "", s)

#: market id -> (stat column, positions modeled, line step)
MARKETS: dict[str, dict] = {
    "pass_yds": {"stat": "pass_yds", "positions": ("QB",), "step": 2.5,
                 "label": "Passing Yards", "unit": "yards"},
    "pass_tds": {"stat": "pass_tds", "positions": ("QB",), "step": 0.5,
                 "label": "Passing TDs", "unit": "touchdowns"},
    "rush_yds": {"stat": "rush_yds", "positions": ("RB", "QB"), "step": 2.5,
                 "label": "Rushing Yards", "unit": "yards"},
    "rec_yds": {"stat": "rec_yds", "positions": ("WR", "TE", "RB"), "step": 2.5,
                "label": "Receiving Yards", "unit": "yards"},
    "receptions": {"stat": "receptions", "positions": ("WR", "TE", "RB"),
                   "step": 0.5, "label": "Receptions", "unit": "catches"},
}

#: factor group -> feature columns (fixed list from the data contract)
FACTOR_GROUPS: dict[str, list[str]] = {
    "recent_form": ["form_mean3", "form_med3", "form_mean5", "form_med5",
                    "form_mean8", "form_med8", "form_season_mean",
                    "form_trend", "games_played_season"],
    "usage_role": ["touches_m3", "touches_m5", "carries_m3", "carries_m5",
                   "targets_m3", "targets_m5", "target_share_l4",
                   "touch_share_l4", "team_targets_l5", "team_carries_l5",
                   "team_touches_l5", "team_pass_share_l5"],
    "opp_defense": ["opp_allowed_std", "opp_allowed_l5",
                    "opp_allowed_pos_std", "opp_rank_allowed"],
    "game_environment": ["vegas_total", "team_implied_pts", "team_spread",
                         "team_points_l5", "week_num"],
    "weather": ["is_dome", "temp_f", "wind_mph", "temp_missing",
                "wind_missing"],
    "rest_schedule": ["rest_days", "rest_diff", "dnp_last_week",
                      "games_missed_l5"],
    "qb_situation": ["qb_prior_starts", "qb_unsettled", "qb_pass_yds_l5",
                     "qb_pass_tds_l5", "team_pass_yds_l5"],
    "home_away": ["is_home_f"],
}

#: M4 position indicators for the pooled markets (rush pools QB+RB, the
#: receiving markets pool WR/TE/RB). The columns are built (build_base) and
#: were evaluated on the 2024 walk-forward split, where they moved MAE/CRPS
#: by < +-0.15% on every pooled market — pure noise, so they are NOT in
#: FEATURES (and per-position models are a fortiori unjustified). The
#: usage/form features evidently already encode position. Kept buildable
#: so validation.py can re-run the experiment.
POSITION_FLAGS: list[str] = ["pos_qb", "pos_rb", "pos_wr", "pos_te"]

#: M9/M10 enrichment feature bundles, validated bundle-wise on the 2024
#: walk-forward split (validation.py --exp enrich). Every bundle is built
#: unconditionally (NaN + missing flag when its source is absent or below
#: the enrich_join coverage gate); FACTOR_GROUPS membership below reflects
#: the 2024 keep/drop decisions.
#:
#: * snaps (M9) — rolling offensive snap share from nflverse snap counts.
#:   All values are strictly as-of (past games only).
SNAP_FEATURES: list[str] = [
    "snap_pct_m3", "snap_pct_m5", "snap_pct_m8", "snap_pct_last",
    "snap_trend", "snap_delta", "snap_missing",
]
#: * air yards / true usage (M9) — rolling target share, air-yards share,
#:   WOPR, aDOT and RACR from nflverse stats_player_week, plus the QB's
#:   rolling passing air yards. Strictly as-of (past games only).
AIR_FEATURES: list[str] = [
    "tgt_share_m3", "tgt_share_m5", "tgt_share_m8", "ay_share_m5",
    "wopr_m3", "wopr_m5", "adot_m5", "racr_m5", "pass_air_m5",
    "air_missing",
]
#: * injuries (M10) — the official report for the PREDICTED week. This is
#:   the one deliberate exception to the strictly-earlier rule: game-status
#:   and practice designations are published before kickoff, so the current
#:   week's report is legitimately known at prediction time (enforced by an
#:   exact same-week join — never a future week; tests assert both).
#:   "Not listed on a filed report" means healthy and is a true 0; only a
#:   missing source yields NaN.
INJURY_FEATURES: list[str] = [
    "inj_questionable", "inj_doubtful", "practice_dnp", "practice_limited",
    "pos_teammates_out", "top3_targets_out",
]
ENRICH_CANDIDATES: list[str] = SNAP_FEATURES + AIR_FEATURES + INJURY_FEATURES

FEATURES: list[str] = [c for cols in FACTOR_GROUPS.values() for c in cols]

META_COLS = ["season", "week", "player_id", "name", "pos", "team", "opp",
             "game_id", "is_home", "played", "has_game", "y",
             "prior_played", "eligible", "ref_blend", "ref_line",
             "elig_targets_m4", "elig_touches_m4", "elig_rush_m8", "qb_name",
             "inj_out"]

#: columns kept in market frames beyond META + FEATURES so the validation
#: harness can score candidate configs without rebuilding frames
EXTRA_BUILDABLE: list[str] = POSITION_FLAGS + [
    c for c in ENRICH_CANDIDATES if c not in FEATURES
]


def _ord(season: pd.Series, week: pd.Series) -> pd.Series:
    """Global time ordinal: strictly increasing across (season, week)."""
    return season * 100 + week


def asof_join(
    base: pd.DataFrame,
    events: pd.DataFrame,
    by: list[str],
    cols: list[str],
) -> pd.DataFrame:
    """Attach the latest strictly-earlier event values to each base row.

    Both frames need an ``ord`` column. Returns the requested event columns
    aligned to ``base``'s original row order (NaN when no earlier event).
    """
    left = base[["ord", *by]].reset_index()  # keep original index
    right = events[["ord", *by, *cols]].dropna(subset=by)
    left = left.sort_values("ord", kind="stable")
    right = right.sort_values("ord", kind="stable")
    merged = pd.merge_asof(
        left, right, on="ord", by=by,
        direction="backward", allow_exact_matches=False,
    )
    return merged.set_index("index").sort_index()[cols]


def _roll(grouped: pd.core.groupby.SeriesGroupBy, window: int, how: str) -> pd.Series:
    """Rolling mean/median/sum including the current row, aligned by index."""
    roller = grouped.rolling(window, min_periods=1)
    if how == "mean":
        out = roller.mean()
    elif how == "sum":
        out = roller.sum()
    else:
        out = roller.median()
    return out.droplevel(list(range(out.index.nlevels - 1)))


def player_form_events(pw: pd.DataFrame, stat: str) -> pd.DataFrame:
    """Per played game: career rolling form of ``stat`` including that game."""
    ev = pw.loc[pw["played"], ["player_id", "season", "week", stat]].copy()
    ev["ord"] = _ord(ev["season"], ev["week"])
    ev = ev.sort_values(["player_id", "ord"])
    g = ev.groupby("player_id")[stat]
    for w in (3, 5, 8):
        ev[f"form_mean{w}"] = _roll(g, w, "mean")
        ev[f"form_med{w}"] = _roll(g, w, "median")
    gs = ev.groupby(["player_id", "season"])[stat]
    ev["form_season_mean"] = gs.transform(lambda s: s.expanding().mean())
    ev["form_season_med"] = gs.transform(lambda s: s.expanding().median())
    return ev


def usage_events(pw: pd.DataFrame) -> pd.DataFrame:
    """Per played game: career rolling usage (touches/carries/targets)."""
    cols = ["touches", "carries", "targets"]
    ev = pw.loc[pw["played"], ["player_id", "season", "week", *cols]].copy()
    ev["ord"] = _ord(ev["season"], ev["week"])
    ev = ev.sort_values(["player_id", "ord"])
    for col in cols:
        g = ev.groupby("player_id")[col]
        ev[f"{col}_m3"] = _roll(g, 3, "mean")
        ev[f"{col}_m5"] = _roll(g, 5, "mean")
        ev[f"{col}_m4"] = _roll(g, 4, "mean")
    rush = pw.loc[pw["played"], ["player_id", "season", "week", "rush_yds"]].copy()
    rush["ord"] = _ord(rush["season"], rush["week"])
    rush = rush.sort_values(["player_id", "ord"])
    ev["rush_m8"] = _roll(rush.groupby("player_id")["rush_yds"], 8, "mean")
    ev["career_played"] = ev.groupby("player_id").cumcount() + 1
    gp = ev.groupby(["player_id", "season"])
    ev["season_played"] = gp.cumcount() + 1
    return ev


def team_events(pw: pd.DataFrame) -> pd.DataFrame:
    """Per team-game: rolling-5 offense volume/scoring including that game."""
    agg = (
        pw[pw["played"] & pw["has_game"]]
        .groupby(["season", "week", "team"], as_index=False)
        .agg(team_targets=("targets", "sum"),
             team_carries=("carries", "sum"),
             team_touches=("touches", "sum"),
             team_pass_yds=("pass_yds", "sum"))
    )
    scores = (
        pw.loc[pw["has_game"], ["season", "week", "team", "team_score"]]
        .drop_duplicates(["season", "week", "team"])
    )
    ev = agg.merge(scores, on=["season", "week", "team"], how="left")
    ev["ord"] = _ord(ev["season"], ev["week"])
    ev = ev.sort_values(["team", "ord"])
    for col, out in [("team_targets", "team_targets_l5"),
                     ("team_carries", "team_carries_l5"),
                     ("team_touches", "team_touches_l5"),
                     ("team_score", "team_points_l5"),
                     ("team_pass_yds", "team_pass_yds_l5")]:
        ev[out] = _roll(ev.groupby("team")[col], 5, "mean")
    for col, out in [("team_targets", "team_targets_l4"),
                     ("team_touches", "team_touches_l4")]:
        ev[out] = _roll(ev.groupby("team")[col], 4, "mean")
    ev["team_pass_share_l5"] = ev["team_targets_l5"] / (
        ev["team_targets_l5"] + ev["team_carries_l5"]
    ).replace(0, np.nan)
    return ev


def qb_form_events(pw: pd.DataFrame) -> pd.DataFrame:
    """Per played QB game: trailing-5 passing form, keyed by normalized name.

    games.csv names each game's starting QB pre-kickoff; joining his own
    trailing production onto a pass-catcher's row gives the M7 "QB quality"
    signal. Events include the game they describe — consumers must as-of
    join with strict inequality (like every other event table here).
    Normalized-name keying matches ``_qb_starts``; the rare same-week
    name collision keeps the higher-volume row.
    """
    qb = pw.loc[(pw["pos"] == "QB") & pw["played"],
                ["name", "season", "week", "pass_yds", "pass_tds"]].copy()
    qb["qb_norm"] = qb["name"].map(norm_name)
    qb["ord"] = _ord(qb["season"], qb["week"])
    qb = (qb.sort_values("pass_yds")
            .drop_duplicates(["qb_norm", "ord"], keep="last")
            .sort_values(["qb_norm", "ord"]))
    qb["qb_pass_yds_l5"] = _roll(qb.groupby("qb_norm")["pass_yds"], 5, "mean")
    qb["qb_pass_tds_l5"] = _roll(qb.groupby("qb_norm")["pass_tds"], 5, "mean")
    return qb


def snap_share_events(snap_games: pd.DataFrame) -> pd.DataFrame:
    """Per snap-counted game: rolling offensive snap share including it.

    ``snap_games`` comes from enrich_join (player_id, season, week,
    offense_pct per game the player logged offensive snaps). Values
    include the game they describe — consumers must as-of join with
    strict inequality, like every other event table here.
    """
    ev = snap_games[["player_id", "season", "week", "offense_pct"]].copy()
    ev["ord"] = _ord(ev["season"], ev["week"])
    ev = ev.sort_values(["player_id", "ord"])
    g = ev.groupby("player_id")["offense_pct"]
    for w in (3, 5, 8):
        ev[f"snap_pct_m{w}"] = _roll(g, w, "mean")
    ev["snap_pct_last"] = ev["offense_pct"]
    return ev


def air_yards_events(air_games: pd.DataFrame) -> pd.DataFrame:
    """Per stats_player_week game: rolling true-usage / air-yards block.

    Shares (target_share, air_yards_share, wopr) roll as plain means;
    aDOT and RACR roll as ratios of 5-game sums so a single low-volume
    week can't blow them up. Events include the game they describe —
    consumers must as-of join with strict inequality.
    """
    ev = air_games.copy()
    ev["ord"] = _ord(ev["season"], ev["week"])
    ev = ev.sort_values(["player_id", "ord"])
    g = ev.groupby("player_id")
    for w in (3, 5, 8):
        ev[f"tgt_share_m{w}"] = _roll(g["target_share"], w, "mean")
    ev["ay_share_m5"] = _roll(g["air_yards_share"], 5, "mean")
    ev["wopr_m3"] = _roll(g["wopr"], 3, "mean")
    ev["wopr_m5"] = _roll(g["wopr"], 5, "mean")
    ev["pass_air_m5"] = _roll(g["passing_air_yards"], 5, "mean")

    rec_ay5 = _roll(g["receiving_air_yards"], 5, "sum")
    targets5 = _roll(g["targets"], 5, "sum")
    rec_yds5 = _roll(g["receiving_yards"], 5, "sum")
    ev["adot_m5"] = rec_ay5 / targets5.replace(0, np.nan)
    # cap RACR: tiny air-yard sums (screen-heavy backs) explode the ratio
    ev["racr_m5"] = (rec_yds5 / rec_ay5.where(rec_ay5 > 0)).clip(-5.0, 10.0)
    return ev


def _attach_enrichment_features(base: pd.DataFrame, pw: pd.DataFrame,
                                enrichment) -> pd.DataFrame:
    """M9/M10 blocks: as-of snap/air rolling features + current-week injuries.

    Snap and air-yards features are strictly as-of (past games only).
    Injury-report features are the documented exception: they join EXACTLY
    on the predicted (season, week) because the official report is
    published pre-kickoff. NaN means "source unavailable / no history";
    injury zeros mean "not listed on a filed report" (healthy) and are
    only written when the source passed its coverage gate.
    """
    if enrichment is None:
        from edgefinder import enrich_join  # deferred: avoids import cycle
        enrichment = enrich_join.attach_enrichment(pw)

    scols = ["snap_pct_m3", "snap_pct_m5", "snap_pct_m8", "snap_pct_last"]
    if enrichment.snap_games is not None and len(enrichment.snap_games):
        sev = snap_share_events(enrichment.snap_games)
        base[scols] = asof_join(base, sev, ["player_id"], scols)
    else:
        base[scols] = np.nan
    base["snap_trend"] = base["snap_pct_m3"] - base["snap_pct_m8"]
    base["snap_delta"] = base["snap_pct_last"] - base["snap_pct_m5"]
    base["snap_missing"] = base["snap_pct_m5"].isna().astype(float)

    acols = ["tgt_share_m3", "tgt_share_m5", "tgt_share_m8", "ay_share_m5",
             "wopr_m3", "wopr_m5", "adot_m5", "racr_m5", "pass_air_m5"]
    if enrichment.air_games is not None and len(enrichment.air_games):
        aev = air_yards_events(enrichment.air_games)
        base[acols] = asof_join(base, aev, ["player_id"], acols)
    else:
        base[acols] = np.nan
    base["air_missing"] = base["tgt_share_m5"].isna().astype(float)

    inj_cols = ["inj_out", "inj_doubtful", "inj_questionable",
                "practice_dnp", "practice_limited"]
    if enrichment.injury_weeks is not None:
        merged = base[["player_id", "season", "week"]].merge(
            enrichment.injury_weeks[["player_id", "season", "week", *inj_cols]],
            on=["player_id", "season", "week"], how="left",
        )
        for c in inj_cols:  # not listed on a filed report = healthy
            base[c] = merged[c].astype(float).fillna(0.0).to_numpy()
    else:
        base[inj_cols] = np.nan

    if enrichment.pos_out_counts is not None:
        merged = base[["season", "week", "team", "pos"]].merge(
            enrichment.pos_out_counts,
            left_on=["season", "week", "team", "pos"],
            right_on=["season", "week", "team", "pos_group"], how="left",
        )
        n_out = merged["n_out"].fillna(0.0).to_numpy()
        # teammates only: a player's own Out never counts itself
        base["pos_teammates_out"] = np.clip(
            n_out - base["inj_out"].fillna(0.0).to_numpy(), 0.0, None)
    else:
        base["pos_teammates_out"] = np.nan

    if enrichment.injury_weeks is not None:
        base["top3_targets_out"] = _top3_targets_out(base)
    else:
        base["top3_targets_out"] = np.nan
    return base


def _top3_targets_out(base: pd.DataFrame) -> np.ndarray:
    """Out-count among the team-week's top-3 trailing-target players.

    "Top 3" ranks the team's players that week by as-of trailing-4
    targets (targets_m4, strictly past weeks); the Out flags are the
    current week's official report. Own Out status never counts —
    the signal is teammates' volume becoming available.
    """
    t = base[["season", "week", "team", "player_id",
              "targets_m4", "inj_out"]].copy()
    t["inj_out"] = t["inj_out"].fillna(0.0)
    t = t[t["targets_m4"].notna() & (t["targets_m4"] > 0)]
    t["rank"] = (t.groupby(["season", "week", "team"])["targets_m4"]
                 .rank(ascending=False, method="first"))
    top3 = t[t["rank"] <= 3]
    agg = (top3.groupby(["season", "week", "team"])["inj_out"].sum()
           .rename("top3_out").reset_index())
    joined = base[["season", "week", "team", "player_id"]].merge(
        agg, on=["season", "week", "team"], how="left")
    total = joined["top3_out"].fillna(0.0).to_numpy()
    in_top3 = base[["season", "week", "team", "player_id"]].merge(
        top3[["season", "week", "team", "player_id"]].assign(_t3=1.0),
        on=["season", "week", "team", "player_id"], how="left",
    )["_t3"].notna().to_numpy()
    own = base["inj_out"].fillna(0.0).to_numpy() * in_top3
    return np.clip(total - own, 0.0, None)


def defense_events(pw: pd.DataFrame, stat: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per defense-game: ``stat`` allowed in total and to each position.

    Returns (overall events, positional events). Values include that game;
    consumers must as-of join with strict inequality.
    """
    played = pw[pw["played"] & pw["has_game"]]
    total = (
        played.groupby(["season", "week", "opp"], as_index=False)[stat]
        .sum()
        .rename(columns={"opp": "defteam", stat: "allowed"})
    )
    total["ord"] = _ord(total["season"], total["week"])
    total = total.sort_values(["defteam", "ord"])
    total["opp_allowed_l5"] = _roll(total.groupby("defteam")["allowed"], 5, "mean")
    gs = total.groupby(["defteam", "season"])["allowed"]
    total["opp_allowed_std"] = gs.transform(lambda s: s.expanding().mean())

    bypos = (
        played.groupby(["season", "week", "opp", "pos"], as_index=False)[stat]
        .sum()
        .rename(columns={"opp": "defteam", stat: "allowed_pos"})
    )
    bypos["ord"] = _ord(bypos["season"], bypos["week"])
    bypos = bypos.sort_values(["defteam", "pos", "ord"])
    gsp = bypos.groupby(["defteam", "season", "pos"])["allowed_pos"]
    bypos["opp_allowed_pos_std"] = gsp.transform(lambda s: s.expanding().mean())
    return total, bypos


def defense_rank_table(def_total: pd.DataFrame) -> pd.DataFrame:
    """As-of weekly rank of season-to-date ``stat`` allowed (1 = most allowed).

    Row (season, week W, defteam) ranks teams on games strictly before W —
    recomputed every week, no end-of-season peeking. Week 1 has no data and
    yields NaN ranks.
    """
    seasons = sorted(def_total["season"].unique())
    teams = sorted(def_total["defteam"].unique())
    weeks = range(1, 19)
    idx = pd.MultiIndex.from_product(
        [seasons, teams, weeks], names=["season", "defteam", "week"]
    )
    std = (
        def_total.set_index(["season", "defteam", "week"])["opp_allowed_std"]
        .reindex(idx)
    )
    grp = std.groupby(level=["season", "defteam"])
    asof = grp.ffill().groupby(level=["season", "defteam"]).shift(1)
    rank = (
        asof.groupby(level=["season", "week"])
        .rank(ascending=False, method="min")
    )
    out = rank.rename("opp_rank_allowed").reset_index()
    return out


def _availability(pw: pd.DataFrame) -> pd.DataFrame:
    """DNP-last-week flag and games missed over the last 5 scheduled weeks."""
    base = pw[["player_id", "season", "week"]].copy()

    sched = pw.loc[pw["has_game"],
                   ["player_id", "season", "week", "played"]].copy()
    prev = sched.rename(columns={"played": "prev_played"})
    prev["week"] = prev["week"] + 1
    base = base.merge(
        prev[["player_id", "season", "week", "prev_played"]],
        on=["player_id", "season", "week"], how="left",
    )
    base["dnp_last_week"] = (base["prev_played"] == False).astype(float)  # noqa: E712

    sched = sched.sort_values(["player_id", "season", "week"])
    sched["missed_cum"] = (~sched["played"]).astype(float)
    sched["missed_cum"] = sched.groupby(["player_id", "season"])["missed_cum"].cumsum()
    sched = sched.rename(columns={"week": "ord"})

    def _asof_week(target_week: pd.Series) -> pd.Series:
        left = pd.DataFrame({
            "ord": target_week.astype(float),
            "player_id": base["player_id"],
            "season": base["season"],
        }).reset_index()
        left = left.sort_values("ord", kind="stable")
        right = sched[["ord", "player_id", "season", "missed_cum"]].copy()
        right["ord"] = right["ord"].astype(float)
        right = right.sort_values("ord", kind="stable")
        m = pd.merge_asof(left, right, on="ord", by=["player_id", "season"],
                          direction="backward", allow_exact_matches=False)
        return m.set_index("index").sort_index()["missed_cum"]

    thru_prev = _asof_week(base["week"]).fillna(0.0)
    thru_m5 = _asof_week(base["week"] - 5).fillna(0.0)
    base["games_missed_l5"] = (thru_prev - thru_m5).clip(lower=0)
    return base[["dnp_last_week", "games_missed_l5"]]


def _qb_starts(pw: pd.DataFrame, games: pd.DataFrame) -> pd.Series:
    """Prior starts this season by the team's listed starting QB.

    games.csv names each game's starter pre-kickoff; the count is over
    strictly earlier weeks of the same season for the same team. For rows
    where the player IS a QB, the caller overrides with his own games
    played this season.
    """
    from edgefinder.load import team_game_long

    tg = team_game_long(games)[["season", "week", "team", "qb_name"]].copy()
    tg = tg.sort_values(["team", "season", "week"])
    tg["qb_prior_starts"] = tg.groupby(["team", "season", "qb_name"]).cumcount()
    joined = pw[["season", "week", "team"]].merge(
        tg[["season", "week", "team", "qb_prior_starts"]],
        on=["season", "week", "team"], how="left",
    )
    return joined["qb_prior_starts"].set_axis(pw.index)


def build_base(pw: pd.DataFrame, games: pd.DataFrame,
               enrichment=None) -> pd.DataFrame:
    """Market-independent features for every player-week row of ``pw``.

    ``enrichment`` is an enrich_join.Enrichment (or None to load the
    cached sources from disk; an Enrichment() with all-None tables builds
    the enrichment columns as NaN + missing flags).
    """
    base = pw.copy()
    base["ord"] = _ord(base["season"], base["week"])

    # -- usage & availability history -----------------------------------
    uev = usage_events(pw)
    ucols = ["touches_m3", "touches_m5", "touches_m4", "carries_m3",
             "carries_m5", "targets_m3", "targets_m5", "targets_m4",
             "rush_m8", "career_played"]
    base[ucols] = asof_join(base, uev, ["player_id"], ucols)
    scols = ["season_played"]
    base[scols] = asof_join(base, uev, ["player_id", "season"], scols)
    base["games_played_season"] = base["season_played"].fillna(0.0)
    base["prior_played"] = base["career_played"].fillna(0.0)
    base = base.drop(columns=["career_played", "season_played"])
    base[["dnp_last_week", "games_missed_l5"]] = _availability(pw).to_numpy()

    # eligibility helpers (as-of, strictly earlier weeks)
    base["elig_targets_m4"] = base["targets_m4"]
    base["elig_touches_m4"] = base["touches_m4"]
    base["elig_rush_m8"] = base["rush_m8"]

    # -- team offense context -------------------------------------------
    tev = team_events(pw)
    tcols = ["team_targets_l5", "team_carries_l5", "team_touches_l5",
             "team_points_l5", "team_pass_share_l5", "team_pass_yds_l5",
             "team_targets_l4", "team_touches_l4"]
    base[tcols] = asof_join(base, tev, ["team"], tcols)
    base["target_share_l4"] = base["targets_m4"] / base["team_targets_l4"].replace(0, np.nan)
    base["touch_share_l4"] = base["touches_m4"] / base["team_touches_l4"].replace(0, np.nan)

    # -- game environment -------------------------------------------------
    base["vegas_total"] = base["total_line"]
    base["team_implied_pts"] = base["implied_pts"]
    base["week_num"] = base["week"].astype(float)
    base["is_home_f"] = base["is_home"].astype(float)

    # -- weather -----------------------------------------------------------
    roof = base["roof"].fillna("")
    base["is_dome"] = roof.isin(["dome", "closed"]).astype(float)
    dome = base["is_dome"] == 1.0
    temp = pd.to_numeric(base["temp"], errors="coerce")
    wind = pd.to_numeric(base["wind"], errors="coerce")
    base["temp_missing"] = (temp.isna() & ~dome).astype(float)
    base["wind_missing"] = (wind.isna() & ~dome).astype(float)
    base["temp_f"] = temp.where(~dome, 68.0).fillna(68.0)
    base["wind_mph"] = wind.where(~dome, 0.0).fillna(0.0)

    # -- rest --------------------------------------------------------------
    base["rest_diff"] = base["rest_days"] - base["opp_rest_days"]

    # -- QB situation --------------------------------------------------------
    starts = _qb_starts(pw, games)
    is_qb = base["pos"] == "QB"
    base["qb_prior_starts"] = starts.where(~is_qb, base["games_played_season"])
    base["qb_unsettled"] = (base["qb_prior_starts"] <= 3).astype(float)

    # M7: the listed starter's own trailing passing form (as-of, strictly
    # earlier weeks), matched by normalized name like _qb_starts.
    qev = qb_form_events(pw)
    base["qb_norm"] = base["qb_name"].map(
        lambda n: norm_name(n) if pd.notna(n) else ""  # "" never matches
    )
    qcols = ["qb_pass_yds_l5", "qb_pass_tds_l5"]
    base[qcols] = asof_join(base, qev, ["qb_norm"], qcols)
    base = base.drop(columns=["qb_norm"])

    # M4: position indicators for the pooled markets
    for p in ("QB", "RB", "WR", "TE"):
        base[f"pos_{p.lower()}"] = (base["pos"] == p).astype(float)

    # M9/M10: snap share + air yards (as-of) and current-week injury report
    base = _attach_enrichment_features(base, pw, enrichment)

    return base


def build_market_frame(
    base: pd.DataFrame, pw: pd.DataFrame, market: str
) -> pd.DataFrame:
    """Feature matrix + metadata for one market over eligible positions."""
    spec = MARKETS[market]
    stat = spec["stat"]
    frame = base[base["pos"].isin(spec["positions"]) & base["has_game"]].copy()

    # -- player form for this stat ----------------------------------------
    fev = player_form_events(pw, stat)
    fcols = ["form_mean3", "form_med3", "form_mean5", "form_med5",
             "form_mean8", "form_med8"]
    frame[fcols] = asof_join(frame, fev, ["player_id"], fcols)
    scols = ["form_season_mean", "form_season_med"]
    frame[scols] = asof_join(frame, fev, ["player_id", "season"], scols)
    frame["form_trend"] = frame["form_mean3"] - frame["form_mean8"]

    # -- opponent defense vs this stat --------------------------------------
    dtot, dpos = defense_events(pw, stat)
    frame = frame.rename(columns={"opp": "defteam"})
    dcols = ["opp_allowed_l5"]
    frame[dcols] = asof_join(frame, dtot, ["defteam"], dcols)
    frame[["opp_allowed_std"]] = asof_join(
        frame, dtot, ["defteam", "season"], ["opp_allowed_std"]
    )
    frame[["opp_allowed_pos_std"]] = asof_join(
        frame, dpos, ["defteam", "season", "pos"], ["opp_allowed_pos_std"]
    )
    frame = frame.rename(columns={"defteam": "opp"})
    ranks = defense_rank_table(dtot)
    frame = frame.merge(
        ranks, left_on=["season", "week", "opp"],
        right_on=["season", "week", "defteam"], how="left",
    ).drop(columns=["defteam"])

    # -- eligibility ---------------------------------------------------------
    pos = frame["pos"]
    if market in ("pass_yds", "pass_tds"):
        frame["eligible"] = pos == "QB"
    elif market == "rush_yds":
        frame["eligible"] = (pos == "RB") | (
            (pos == "QB") & (frame["elig_rush_m8"] >= 15.0)
        )
    else:  # rec_yds / receptions: WR & TE always, RB needs target volume
        frame["eligible"] = pos.isin(["WR", "TE"]) | (
            (pos == "RB") & (frame["elig_targets_m4"] >= 2.5)
        )

    # -- target & fan reference line -----------------------------------------
    frame["y"] = frame[stat]
    blend = frame[["form_med5", "form_season_med"]].mean(axis=1, skipna=True)
    frame["ref_blend"] = blend
    frame["ref_line"] = snap_ref_line(blend, market)

    keep = ([c for c in META_COLS if c in frame.columns] + FEATURES
            + [c for c in EXTRA_BUILDABLE if c in frame.columns])
    return frame[keep].reset_index(drop=True)


def snap_ref_line(blend: pd.Series, market: str) -> pd.Series:
    """Snap the fan-expectation blend to a half-point line.

    Yards/receptions: nearest value ending in .5 (249.9 -> 249.5). Pass TDs:
    nearest of {0.5, 1.5, 2.5, 3.5}. Lines are floored at 0.5.
    """
    if market == "pass_tds":
        snapped = (blend - 0.5).round(0) + 0.5
        return snapped.clip(lower=0.5, upper=3.5)
    snapped = (blend - 0.5).round(0) + 0.5
    return snapped.clip(lower=0.5)


def build_all_frames(
    pw: pd.DataFrame, games: pd.DataFrame, enrichment=None
) -> dict[str, pd.DataFrame]:
    """Base features once, then one frame per market."""
    base = build_base(pw, games, enrichment)
    return {m: build_market_frame(base, pw, m) for m in MARKETS}
