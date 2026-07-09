"""Leak-sensitive helpers: rolling form and opponent ranks must be as-of."""

import numpy as np
import pandas as pd

from edgefinder.features import (
    asof_join,
    defense_events,
    defense_rank_table,
    player_form_events,
    qb_form_events,
)


def _mini_pw() -> pd.DataFrame:
    """One player, one season, five weeks, pass_yds 100..500, all played."""
    return pd.DataFrame({
        "player_id": ["p1"] * 5,
        "season": [2023] * 5,
        "week": [1, 2, 3, 4, 5],
        "pass_yds": [100.0, 200.0, 300.0, 400.0, 500.0],
        "played": [True] * 5,
    })


def test_rolling_form_excludes_current_week():
    pw = _mini_pw()
    ev = player_form_events(pw, "pass_yds")
    base = pw.copy()
    base["ord"] = base["season"] * 100 + base["week"]
    got = asof_join(base, ev, ["player_id"], ["form_mean3"])

    # week 1: no history; week 4 sees only weeks 1-3; week 5 sees 2-4
    assert np.isnan(got["form_mean3"].iloc[0])
    assert got["form_mean3"].iloc[3] == 200.0  # mean(100,200,300)
    assert got["form_mean3"].iloc[4] == 300.0  # mean(200,300,400)
    # never includes the same-week value
    assert got["form_mean3"].iloc[4] != np.mean([300.0, 400.0, 500.0])


def test_dnp_games_are_not_form_events():
    pw = _mini_pw()
    pw.loc[2, "played"] = False  # week 3 DNP
    ev = player_form_events(pw, "pass_yds")
    base = pw.copy()
    base["ord"] = base["season"] * 100 + base["week"]
    got = asof_join(base, ev, ["player_id"], ["form_mean3"])
    # week 4 sees played weeks 1,2 only -> mean(100,200)
    assert got["form_mean3"].iloc[3] == 150.0


def test_qb_form_features_are_strictly_prior():
    """M7: the starting QB's trailing form must exclude the current week."""
    pw = pd.DataFrame({
        "player_id": ["q1"] * 4,
        "name": ["Joe Slinger Jr."] * 4,
        "pos": ["QB"] * 4,
        "season": [2023] * 4,
        "week": [1, 2, 3, 4],
        "pass_yds": [100.0, 200.0, 300.0, 400.0],
        "pass_tds": [1.0, 2.0, 3.0, 4.0],
        "played": [True] * 4,
    })
    ev = qb_form_events(pw)
    assert set(ev["qb_norm"]) == {"joeslinger"}  # suffix stripped
    # a pass-catcher row whose listed starter is Joe, week 3
    base = pd.DataFrame({"qb_norm": ["joeslinger"], "season": [2023],
                         "week": [3]})
    base["ord"] = base["season"] * 100 + base["week"]
    got = asof_join(base, ev, ["qb_norm"], ["qb_pass_yds_l5", "qb_pass_tds_l5"])
    assert got["qb_pass_yds_l5"].iloc[0] == 150.0  # mean(100, 200), no wk3
    assert got["qb_pass_tds_l5"].iloc[0] == 1.5


def _mini_def_pw() -> pd.DataFrame:
    """Two defenses over three weeks with distinct allowed totals."""
    rows = []
    for week, (a_allowed, b_allowed) in enumerate([(100, 300), (300, 100),
                                                   (500, 100)], start=1):
        rows.append({"season": 2023, "week": week, "opp": "AAA", "pos": "QB",
                     "pass_yds": float(a_allowed), "played": True,
                     "has_game": True})
        rows.append({"season": 2023, "week": week, "opp": "BBB", "pos": "QB",
                     "pass_yds": float(b_allowed), "played": True,
                     "has_game": True})
    return pd.DataFrame(rows)


def test_opponent_rank_is_as_of_week():
    dtot, _ = defense_events(_mini_def_pw(), "pass_yds")
    ranks = defense_rank_table(dtot)
    r = ranks.set_index(["season", "week", "defteam"])["opp_rank_allowed"]

    # week 1: no prior games -> NaN
    assert np.isnan(r.loc[(2023, 1, "AAA")])
    # week 2 uses week 1 only: BBB allowed 300 > AAA 100 -> BBB rank 1
    assert r.loc[(2023, 2, "BBB")] == 1.0
    assert r.loc[(2023, 2, "AAA")] == 2.0
    # week 3 uses weeks 1-2 (means 200 both) -> tie, but NOT week 3's 500
    assert r.loc[(2023, 3, "AAA")] == r.loc[(2023, 3, "BBB")] == 1.0


def test_defense_std_mean_is_strictly_prior():
    dtot, _ = defense_events(_mini_def_pw(), "pass_yds")
    base = pd.DataFrame({
        "defteam": ["AAA"], "season": [2023], "week": [3],
    })
    base["ord"] = base["season"] * 100 + base["week"]
    got = asof_join(base, dtot, ["defteam", "season"], ["opp_allowed_std"])
    assert got["opp_allowed_std"].iloc[0] == 200.0  # mean(100, 300), no wk3
