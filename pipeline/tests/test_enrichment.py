"""M9/M10/M13 enrichment: join normalizer, leak-freedom, mirror resolution.

Covers the four risk areas of the enrichment layer:
* the cross-source name normalizer (suffixes, punctuation, accents),
* the two-stage join (team-mismatch rescue must never guess between
  ambiguous same-named players),
* leak-freedom: snap/air rolling features must exclude the current week,
  while injury-report features must come from EXACTLY the current week
  (pre-kickoff info) and never a future one,
* enrich.py source resolution: canonical URL first, pinned mirrors after,
  and the git ls-remote pin-refresh parser.
"""

import numpy as np
import pandas as pd
import pytest

from edgefinder import enrich
from edgefinder.enrich_join import (
    Enrichment,
    JoinCoverage,
    _verify_team_codes,
    norm_join_name,
    two_stage_join,
)
from edgefinder.features import (
    AIR_FEATURES,
    INJURY_FEATURES,
    SNAP_FEATURES,
    _attach_enrichment_features,
    air_yards_events,
    asof_join,
    snap_share_events,
)


# ---------------------------------------------------------------------------
# normalizer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("Marvin Jones Jr.", "Marvin Jones"),
    ("Odell Beckham Jr.", "odell beckham"),
    ("D.J. Moore", "DJ Moore"),
    ("Amon-Ra St. Brown", "Amon-Ra St.Brown"),
    ("KaVontae Turpin", "Kavontae Turpin"),
    ("Ja'Marr Chase", "JaMarr Chase"),
    ("Gardner Minshew II", "Gardner Minshew"),
])
def test_norm_join_name_bridges_source_drift(a, b):
    assert norm_join_name(a) == norm_join_name(b)


def test_norm_join_name_keeps_distinct_players_apart():
    assert norm_join_name("Mike Williams") != norm_join_name("Mike Evans")


# ---------------------------------------------------------------------------
# two-stage join
# ---------------------------------------------------------------------------

def _pw_keys(rows):
    df = pd.DataFrame(rows, columns=["player_id", "name", "team",
                                     "season", "week"])
    df["norm"] = df["name"].map(norm_join_name)
    return df


def _src(rows):
    df = pd.DataFrame(rows, columns=["name", "team", "season", "week", "val"])
    df["norm"] = df["name"].map(norm_join_name)
    return df


def test_stage1_exact_team_match():
    keys = _pw_keys([("1", "Joe Star", "KC", 2024, 3)])
    src = _src([("Joe Star", "KC", 2024, 3, 0.9)])
    out = two_stage_join(keys, src, ["val"])
    assert out["val"].iloc[0] == 0.9
    assert out["join_stage"].iloc[0] == 1


def test_stage2_rescues_retro_team_mismatch():
    # hvpkod retro-applies the end-of-season team (SF); the source carries
    # the true per-week team (CAR). Name-only fallback must recover it.
    keys = _pw_keys([("1", "Christian McCaffrey", "SF", 2022, 3)])
    src = _src([("Christian McCaffrey", "CAR", 2022, 3, 0.8)])
    out = two_stage_join(keys, src, ["val"])
    assert out["val"].iloc[0] == 0.8
    assert out["join_stage"].iloc[0] == 2


def test_stage2_never_guesses_between_ambiguous_names():
    # two different Ryan Griffins in the same week: no team match on either
    # side -> the fallback must refuse (ambiguous on the pw side)
    keys = _pw_keys([
        ("1", "Ryan Griffin", "TB", 2021, 1),
        ("2", "Ryan Griffin", "NYJ", 2021, 1),
    ])
    src = _src([("Ryan Griffin", "HOU", 2021, 1, 0.5)])
    out = two_stage_join(keys, src, ["val"])
    assert out["val"].isna().all()
    # and ambiguity on the SOURCE side also blocks the fallback
    keys2 = _pw_keys([("1", "Ryan Griffin", "TB", 2021, 1)])
    src2 = _src([
        ("Ryan Griffin", "HOU", 2021, 1, 0.5),
        ("Ryan Griffin", "NO", 2021, 1, 0.7),
    ])
    out2 = two_stage_join(keys2, src2, ["val"])
    assert out2["val"].isna().all()


def test_verify_team_codes_raises_without_resolution_path():
    src = pd.DataFrame({"team": ["XYZ"], "val": [1.0]})
    with pytest.raises(ValueError, match="XYZ"):
        _verify_team_codes(src, "test", {"KC", "BUF"})


def test_coverage_gate():
    ok = JoinCoverage("s", {2021: 0.95, 2022: 0.99}, "rows", 100)
    bad = JoinCoverage("s", {2021: 0.95, 2022: 0.89}, "rows", 100)
    assert ok.ok and not bad.ok


# ---------------------------------------------------------------------------
# leak-freedom: rolling enrichment features are strictly as-of
# ---------------------------------------------------------------------------

def _mini_base(weeks=(1, 2, 3, 4, 5)):
    base = pd.DataFrame({
        "player_id": ["p1"] * len(weeks),
        "season": [2023] * len(weeks),
        "week": list(weeks),
        "team": ["KC"] * len(weeks),
        "pos": ["WR"] * len(weeks),
        "targets_m4": [5.0] * len(weeks),
    })
    base["ord"] = base["season"] * 100 + base["week"]
    return base


def test_snap_rolling_excludes_current_week():
    snap_games = pd.DataFrame({
        "player_id": ["p1"] * 5,
        "season": [2023] * 5,
        "week": [1, 2, 3, 4, 5],
        "offense_pct": [0.1, 0.2, 0.3, 0.4, 0.5],
    })
    ev = snap_share_events(snap_games)
    got = asof_join(_mini_base(), ev, ["player_id"],
                    ["snap_pct_m3", "snap_pct_last"])
    assert np.isnan(got["snap_pct_m3"].iloc[0])          # week 1: no history
    assert got["snap_pct_last"].iloc[1] == pytest.approx(0.1)  # last game only
    assert got["snap_pct_m3"].iloc[3] == pytest.approx(0.2)    # mean(w1..w3)
    # never includes the same-week value
    assert got["snap_pct_m3"].iloc[4] != pytest.approx(np.mean([0.3, 0.4, 0.5]))


def test_air_rolling_excludes_current_week_and_uses_ratio_of_sums():
    air_games = pd.DataFrame({
        "player_id": ["p1"] * 3,
        "season": [2023] * 3,
        "week": [1, 2, 3],
        "target_share": [0.10, 0.20, 0.30],
        "air_yards_share": [0.1, 0.2, 0.3],
        "wopr": [0.2, 0.4, 0.6],
        "racr": [1.0, 1.0, 1.0],
        "receiving_air_yards": [50.0, 100.0, 150.0],
        "passing_air_yards": [np.nan] * 3,
        "receiving_yards": [40.0, 90.0, 140.0],
        "targets": [5.0, 10.0, 15.0],
    })
    ev = air_yards_events(air_games)
    got = asof_join(_mini_base((1, 2, 3)), ev, ["player_id"],
                    ["tgt_share_m3", "adot_m5", "racr_m5"])
    assert np.isnan(got["tgt_share_m3"].iloc[0])
    assert got["tgt_share_m3"].iloc[2] == pytest.approx(0.15)  # mean(w1, w2)
    # aDOT at week 3 = (50+100)/(5+10), never including week 3
    assert got["adot_m5"].iloc[2] == pytest.approx(10.0)
    assert got["racr_m5"].iloc[2] == pytest.approx(130.0 / 150.0)


def test_racr_capped_when_air_yards_tiny():
    air_games = pd.DataFrame({
        "player_id": ["p1"], "season": [2023], "week": [1],
        "target_share": [0.1], "air_yards_share": [0.0], "wopr": [0.1],
        "racr": [np.nan], "receiving_air_yards": [0.5],
        "passing_air_yards": [np.nan], "receiving_yards": [60.0],
        "targets": [3.0],
    })
    ev = air_yards_events(air_games)
    assert ev["racr_m5"].iloc[0] == pytest.approx(10.0)  # capped, not 120


# ---------------------------------------------------------------------------
# injuries: current-week only — never future, never rolled
# ---------------------------------------------------------------------------

def _injury_weeks(rows):
    return pd.DataFrame(rows, columns=[
        "player_id", "season", "week", "inj_out", "inj_doubtful",
        "inj_questionable", "practice_dnp", "practice_limited"])


def test_injury_status_applies_to_exactly_its_own_week():
    base = _mini_base((1, 2, 3))
    enr = Enrichment(injury_weeks=_injury_weeks([
        ("p1", 2023, 2, 0.0, 0.0, 1.0, 0.0, 1.0),
    ]))
    out = _attach_enrichment_features(base.copy(), base, enr)
    # week 2 (the report's own week) carries the status — pre-kickoff info
    assert out.loc[out["week"] == 2, "inj_questionable"].iloc[0] == 1.0
    assert out.loc[out["week"] == 2, "practice_limited"].iloc[0] == 1.0
    # weeks 1 and 3 are untouched: a report never leaks backward OR forward
    assert (out.loc[out["week"] != 2, "inj_questionable"] == 0.0).all()
    assert (out.loc[out["week"] != 2, "practice_limited"] == 0.0).all()


def test_future_injury_report_cannot_affect_earlier_weeks():
    base = _mini_base((1, 2, 3))
    quiet = Enrichment(injury_weeks=_injury_weeks([]))
    noisy = Enrichment(injury_weeks=_injury_weeks([
        ("p1", 2023, 3, 1.0, 0.0, 0.0, 1.0, 0.0),  # week-3 Out report
    ]))
    a = _attach_enrichment_features(base.copy(), base, quiet)
    b = _attach_enrichment_features(base.copy(), base, noisy)
    early = ["inj_questionable", "inj_doubtful", "practice_dnp",
             "practice_limited", "inj_out"]
    pd.testing.assert_frame_equal(
        a.loc[a["week"] < 3, early], b.loc[b["week"] < 3, early])


def test_not_listed_is_zero_but_missing_source_is_nan():
    base = _mini_base((1,))
    listed = _attach_enrichment_features(
        base.copy(), base, Enrichment(injury_weeks=_injury_weeks([])))
    assert listed["inj_questionable"].iloc[0] == 0.0  # filed report, not on it
    absent = _attach_enrichment_features(base.copy(), base, Enrichment())
    assert np.isnan(absent["inj_questionable"].iloc[0])  # no source: explicit
    assert np.isnan(absent["snap_pct_m5"].iloc[0])
    assert absent["snap_missing"].iloc[0] == 1.0
    assert absent["air_missing"].iloc[0] == 1.0


def test_top3_targets_out_counts_teammates_not_self():
    base = pd.DataFrame({
        "player_id": ["a", "b", "c", "d"],
        "season": [2023] * 4,
        "week": [5] * 4,
        "team": ["KC"] * 4,
        "pos": ["WR"] * 4,
        "targets_m4": [9.0, 7.0, 5.0, 1.0],  # top-3 = a, b, c
    })
    base["ord"] = base["season"] * 100 + base["week"]
    enr = Enrichment(injury_weeks=_injury_weeks([
        ("a", 2023, 5, 1.0, 0.0, 0.0, 1.0, 0.0),  # top target ruled Out
    ]))
    out = _attach_enrichment_features(base.copy(), base, enr)
    by_id = out.set_index("player_id")["top3_targets_out"]
    assert by_id["b"] == 1.0 and by_id["c"] == 1.0 and by_id["d"] == 1.0
    assert by_id["a"] == 0.0  # own Out never counts itself


def test_enrich_candidate_columns_all_produced():
    base = _mini_base()
    out = _attach_enrichment_features(base.copy(), base, Enrichment())
    for col in SNAP_FEATURES + AIR_FEATURES + INJURY_FEATURES:
        assert col in out.columns, col


# ---------------------------------------------------------------------------
# enrich.py: source URL resolution + mirror pins
# ---------------------------------------------------------------------------

def test_urls_prefer_canonical_then_pinned_mirror():
    ds = enrich.DATASETS["snap_counts"]
    urls = ds.urls(2023)
    assert urls[0].startswith(
        "https://github.com/nflverse/nflverse-data/releases/download/")
    assert "snap_counts_2023.csv.gz" in urls[0]
    assert urls[1].startswith("https://raw.githubusercontent.com/dachhack/stathead/")
    assert enrich.MIRROR_PINS["dachhack/stathead"] in urls[1]


def test_props_are_mirror_only_and_pinned():
    for key in ("props_pass_yds", "props_receptions"):
        ds = enrich.DATASETS[key]
        assert ds.canonical is None
        (url,) = ds.urls()
        assert enrich.MIRROR_PINS["firstandthirty/nfl-tools"] in url
        assert url.endswith(".csv")


def test_player_stats_mirror_maps_to_local_name(tmp_path):
    ds = enrich.DATASETS["player_stats"]
    assert "nflverse_stats_player_week_{season}" in ds.mirrors[0]
    # local cache name stays canonical regardless of the mirror's name
    assert ds.dest(tmp_path, 2024).name == "stats_player_week_2024.csv"


def test_parse_ls_remote_head():
    sha = "9d6bdecbb00e5b4d5473f1b37ff669d74e849bb9"
    out = f"{sha}\tHEAD\n0000000000000000000000000000000000000000\trefs/pull/1\n"
    assert enrich.parse_ls_remote_head(out) == sha
    assert enrich.parse_ls_remote_head("") is None


def test_refresh_mirror_pin_uses_git_ls_remote(monkeypatch):
    sha = "a" * 40
    calls = {}

    class FakeCompleted:
        stdout = f"{sha}\tHEAD\n"

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return FakeCompleted()

    monkeypatch.setattr(enrich.subprocess, "run", fake_run)
    assert enrich.refresh_mirror_pin("owner/repo") == sha
    assert calls["cmd"][:2] == ["git", "ls-remote"]
    assert calls["cmd"][2] == "https://github.com/owner/repo"
