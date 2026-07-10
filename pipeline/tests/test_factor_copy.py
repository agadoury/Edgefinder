"""U11: factor headlines must agree with their arrows.

Every factor headline is emitted from ``explain.HEADLINE_TEMPLATES``, a
registry in which each template declares the direction its stat framing
implies (up / down / neutral / contrast). These tests rebuild a polarity
classifier from that same registry — never from ad-hoc string heuristics —
and walk every exported factor: a headline may match its arrow, be an
explicit contrast form, or be neutral; it may never assert the opposite
direction of its own impact sign.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pandas as pd
import pytest

from edgefinder.explain import (
    HEADLINE_TEMPLATES,
    classify_headline,
    match_templates,
    render_factor,
)

ROOT = Path(__file__).resolve().parent.parent.parent
EXPORT_DIRS = [
    d for d in (ROOT / "pipeline" / "data" / "export", ROOT / "src" / "data")
    if (d / "players").is_dir()
]
NAN = float("nan")


# ---------------------------------------------------------------------------
# registry sanity: the classifier is built from template metadata
# ---------------------------------------------------------------------------

def test_registry_polarities_are_valid():
    assert HEADLINE_TEMPLATES, "template registry is empty"
    for name, t in HEADLINE_TEMPLATES.items():
        assert t.polarity in {"up", "down", "neutral", "contrast"}, name
    fmts = [t.fmt for t in HEADLINE_TEMPLATES.values()]
    assert len(set(fmts)) == len(fmts), "duplicate template format strings"


def test_template_instantiations_classify_unambiguously():
    """Any instantiation of a template must map back to a single polarity."""
    for name, t in HEADLINE_TEMPLATES.items():
        fields = re.findall(r"\{([a-z0-9_]+)\}", t.fmt)
        label = t.fmt.format(**{f: "7" for f in fields})
        matched = match_templates(label)
        assert name in matched, f"{name}: does not match its own pattern"
        assert classify_headline(label) == t.polarity, (
            f"{name}: ambiguous across polarities, matched {matched}")


# ---------------------------------------------------------------------------
# renderer: mismatch switches to contrast, or neutral without a counter
# ---------------------------------------------------------------------------

def _row(**kw) -> pd.Series:
    base = {"pos": "WR", "team": "CIN", "opp": "BUF"}
    base.update(kw)
    return pd.Series(base)


#: (group, market, row overrides, medians, impact, expected template)
CASES = [
    # opp_defense: stingy stat + up impact -> contrast via recent form
    ("opp_defense", "rec_yds",
     dict(opp_allowed_std=177.0, opp_rank_allowed=32.0, opp_allowed_l5=210.0,
          opp_allowed_pos_std=50.0),
     {"opp_allowed_pos_std": 45.0}, +13.7, "def_contrast"),
    # ... stingy + up but positional split carries the story
    ("opp_defense", "rec_yds",
     dict(opp_allowed_std=177.0, opp_rank_allowed=32.0, opp_allowed_l5=170.0,
          opp_allowed_pos_std=50.0),
     {"opp_allowed_pos_std": 45.0}, +13.7, "def_contrast"),
    # ... stingy + up with no supporting signal -> neutral fallback
    ("opp_defense", "rec_yds",
     dict(opp_allowed_std=177.0, opp_rank_allowed=32.0, opp_allowed_l5=170.0,
          opp_allowed_pos_std=40.0),
     {"opp_allowed_pos_std": 45.0}, +13.7, "def_neutral"),
    # ... stingy + down impact: framing matches the arrow, keep the stat
    ("opp_defense", "rec_yds",
     dict(opp_allowed_std=177.0, opp_rank_allowed=32.0, opp_allowed_l5=170.0,
          opp_allowed_pos_std=40.0),
     {"opp_allowed_pos_std": 45.0}, -6.0, "def_stingy"),
    # ... generous + down impact -> contrast (tightened up lately)
    ("opp_defense", "rec_yds",
     dict(opp_allowed_std=260.0, opp_rank_allowed=1.0, opp_allowed_l5=220.0,
          opp_allowed_pos_std=60.0),
     {"opp_allowed_pos_std": 45.0}, -6.0, "def_contrast"),
    # ... generous + up impact matches
    ("opp_defense", "rec_yds",
     dict(opp_allowed_std=260.0, opp_rank_allowed=1.0, opp_allowed_l5=260.0,
          opp_allowed_pos_std=60.0),
     {"opp_allowed_pos_std": 45.0}, +6.0, "def_generous"),
    # ... no rank yet -> neutral framing, either arrow is fine
    ("opp_defense", "rec_yds",
     dict(opp_allowed_std=200.0, opp_rank_allowed=NAN, opp_allowed_l5=NAN,
          opp_allowed_pos_std=NAN), {}, +6.0, "def_unranked"),
    # recent_form: cooled off + up impact -> contrast
    ("recent_form", "receptions",
     dict(form_mean3=5.3, form_mean8=8.1), {}, +2.6, "form_contrast_cold"),
    # ... heating up + down impact -> contrast
    ("recent_form", "rec_yds",
     dict(form_mean3=45.0, form_mean8=30.0), {}, -3.0, "form_contrast_hot"),
    # ... trend matches arrow -> directional stat headline
    ("recent_form", "rec_yds",
     dict(form_mean3=95.0, form_mean8=70.0), {}, +12.0, "form_hot"),
    ("recent_form", "rec_yds",
     dict(form_mean3=40.0, form_mean8=70.0), {}, -12.0, "form_cold"),
    # ... no material trend -> plain neutral headline
    ("recent_form", "rec_yds",
     dict(form_mean3=70.5, form_mean8=70.0), {}, -12.0, "form_plain"),
    ("recent_form", "rec_yds",
     dict(form_mean3=NAN, form_mean8=NAN), {}, +2.0, "form_plain"),
    # usage_role: heavy targets + down impact, share below median -> contrast
    ("usage_role", "rec_yds",
     dict(elig_targets_m4=12.8, target_share_l4=0.18, team_targets_l5=30.0),
     {"targets_m5": 6.0, "target_share_l4": 0.25, "team_targets_l5": 33.0},
     -4.0, "usage_contrast_down"),
    # ... light targets + up impact, share above median -> contrast
    ("usage_role", "rec_yds",
     dict(elig_targets_m4=3.0, target_share_l4=0.30, team_targets_l5=36.0),
     {"targets_m5": 6.0, "target_share_l4": 0.25, "team_targets_l5": 33.0},
     +4.0, "usage_contrast_up"),
    # ... heavy + down with nothing supporting the flip -> neutral
    ("usage_role", "rec_yds",
     dict(elig_targets_m4=12.8, target_share_l4=0.30, team_targets_l5=36.0),
     {"targets_m5": 6.0, "target_share_l4": 0.25, "team_targets_l5": 33.0},
     -4.0, "usage_neutral"),
    # ... heavy + up matches
    ("usage_role", "rec_yds",
     dict(elig_targets_m4=12.8, target_share_l4=0.30, team_targets_l5=36.0),
     {"targets_m5": 6.0}, +4.0, "usage_heavy"),
    # ... middling usage -> plain neutral headline either way
    ("usage_role", "rec_yds",
     dict(elig_targets_m4=6.0), {"targets_m5": 6.0}, -4.0,
     "usage_targets_plain"),
    # ... rush touches variant
    ("usage_role", "rush_yds",
     dict(pos="RB", elig_touches_m4=19.0, touch_share_l4=0.2,
          team_carries_l5=22.0),
     {"touches_m5": 12.0, "touch_share_l4": 0.35, "team_carries_l5": 26.0},
     -4.0, "usage_contrast_down"),
    # ... QB team volume has no share counter-story -> neutral on mismatch
    ("usage_role", "pass_yds",
     dict(pos="QB", team_targets_l5=40.0), {"team_targets_l5": 33.0},
     -8.0, "usage_neutral"),
    ("usage_role", "pass_yds",
     dict(pos="QB", team_targets_l5=40.0), {"team_targets_l5": 33.0},
     +8.0, "usage_volume_high"),
    # game_environment: big total + down impact, underdog side -> contrast
    ("game_environment", "rec_yds",
     dict(vegas_total=54.5, team_implied_pts=24.0), {"vegas_total": 45.0},
     -4.0, "env_contrast_down"),
    # ... big total + down impact, favored side -> neutral fallback
    ("game_environment", "rec_yds",
     dict(vegas_total=54.5, team_implied_pts=30.5), {"vegas_total": 45.0},
     -4.0, "env_neutral"),
    # ... quiet total + up impact, team owns most of it -> contrast
    ("game_environment", "rec_yds",
     dict(vegas_total=38.0, team_implied_pts=22.0), {"vegas_total": 45.0},
     +4.0, "env_contrast_up"),
    # ... matched and mid-total cases
    ("game_environment", "rec_yds",
     dict(vegas_total=54.5, team_implied_pts=30.5), {"vegas_total": 45.0},
     +4.0, "env_high"),
    ("game_environment", "rec_yds",
     dict(vegas_total=45.5, team_implied_pts=23.0), {"vegas_total": 45.0},
     -4.0, "env_plain"),
    ("game_environment", "rec_yds",
     dict(vegas_total=NAN, team_implied_pts=NAN), {}, +4.0, "env_missing"),
    # weather: wind + up impact on a rushing market -> run-tilt contrast
    ("weather", "rush_yds",
     dict(pos="RB", is_dome=0.0, wind_mph=16.0, temp_f=50.0), {}, +3.0,
     "wx_contrast_run"),
    # ... wind + up impact elsewhere: no honest counter -> neutral
    ("weather", "rec_yds",
     dict(is_dome=0.0, wind_mph=16.0, temp_f=50.0), {}, +3.0, "wx_neutral"),
    ("weather", "rec_yds",
     dict(is_dome=0.0, wind_mph=16.0, temp_f=50.0), {}, -3.0, "wx_wind"),
    ("weather", "rec_yds",
     dict(is_dome=0.0, wind_mph=5.0, temp_f=25.0), {}, -3.0, "wx_cold"),
    ("weather", "rec_yds",
     dict(is_dome=0.0, wind_mph=5.0, temp_f=25.0), {}, +3.0, "wx_neutral"),
    ("weather", "rec_yds",
     dict(is_dome=1.0), {}, +3.0, "wx_dome"),
    ("weather", "rec_yds",
     dict(is_dome=0.0, wind_mph=5.0, temp_f=60.0), {}, -3.0, "wx_fair"),
    # rest_schedule / M10: current-week injury stories outrank the rest
    ("rest_schedule", "rec_yds",
     dict(inj_questionable=1.0, practice_limited=1.0, dnp_last_week=1.0),
     {}, -3.0, "inj_listed"),
    ("rest_schedule", "rec_yds",
     dict(inj_doubtful=1.0, practice_dnp=1.0), {}, +3.0,
     "inj_listed_neutral"),
    ("rest_schedule", "rec_yds",
     dict(top3_targets_out=1.0, dnp_last_week=0.0, games_missed_l5=0.0,
          rest_days=7.0, rest_diff=0.0), {}, +3.0, "inj_top_out"),
    ("rest_schedule", "rec_yds",
     dict(top3_targets_out=2.0, dnp_last_week=0.0, games_missed_l5=0.0,
          rest_days=7.0, rest_diff=0.0), {}, -3.0, "inj_top_out_neutral"),
    # rest_schedule: sat out + up impact -> neutral (nothing explains it)
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=1.0), {}, +3.0, "rest_dnp_neutral"),
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=1.0), {}, -3.0, "rest_dnp"),
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=2.0), {}, +3.0,
     "rest_missed_neutral"),
    # ... short week + up impact with the rest edge -> contrast
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=0.0, rest_days=5.0,
          rest_diff=1.0), {}, +3.0, "rest_short_contrast"),
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=0.0, rest_days=5.0,
          rest_diff=-1.0), {}, +3.0, "rest_neutral"),
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=0.0, rest_days=5.0,
          rest_diff=-1.0), {}, -3.0, "rest_short"),
    # ... extra rest + down impact -> neutral
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=0.0, rest_days=10.0,
          rest_diff=4.0), {}, -3.0, "rest_neutral"),
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=0.0, rest_days=10.0,
          rest_diff=4.0), {}, +3.0, "rest_long"),
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=0.0, rest_days=6.0,
          rest_diff=-3.0), {}, -3.0, "rest_edge_opp"),
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=0.0, rest_days=6.0,
          rest_diff=-3.0), {}, +3.0, "rest_neutral"),
    ("rest_schedule", "rec_yds",
     dict(dnp_last_week=0.0, games_missed_l5=0.0, rest_days=7.0,
          rest_diff=0.0), {}, +3.0, "rest_standard"),
    # qb_situation: few starts + up impact, producing -> contrast
    ("qb_situation", "pass_yds",
     dict(pos="QB", qb_prior_starts=2.0, qb_pass_yds_l5=280.0),
     {"qb_pass_yds_l5": 220.0}, +8.0, "qb_self_contrast"),
    ("qb_situation", "pass_yds",
     dict(pos="QB", qb_prior_starts=2.0, qb_pass_yds_l5=180.0),
     {"qb_pass_yds_l5": 220.0}, +8.0, "qb_self_neutral"),
    ("qb_situation", "pass_yds",
     dict(pos="QB", qb_prior_starts=2.0, qb_pass_yds_l5=180.0),
     {"qb_pass_yds_l5": 220.0}, -8.0, "qb_self_new"),
    ("qb_situation", "pass_yds",
     dict(pos="QB", qb_prior_starts=12.0), {}, -8.0, "qb_self_vet"),
    ("qb_situation", "receptions",
     dict(qb_prior_starts=3.0, qb_name="Joe Burrow", qb_pass_yds_l5=280.0),
     {"qb_pass_yds_l5": 220.0}, +0.5, "qb_other_contrast"),
    ("qb_situation", "receptions",
     dict(qb_prior_starts=3.0, qb_name="Joe Burrow", qb_pass_yds_l5=180.0),
     {"qb_pass_yds_l5": 220.0}, +0.5, "qb_other_neutral"),
    ("qb_situation", "receptions",
     dict(qb_prior_starts=3.0, qb_name="Joe Burrow", qb_pass_yds_l5=180.0),
     {"qb_pass_yds_l5": 220.0}, -0.5, "qb_other_new"),
    ("qb_situation", "receptions",
     dict(qb_prior_starts=12.0, qb_name="Joe Burrow"), {}, -0.5,
     "qb_other_vet"),
    # home_away: no counter features -> neutral on any mismatch
    ("home_away", "receptions", dict(is_home_f=1.0), {}, +0.5, "venue_home"),
    ("home_away", "receptions", dict(is_home_f=1.0), {}, -0.5,
     "venue_home_neutral"),
    ("home_away", "receptions", dict(is_home_f=0.0), {}, -0.5, "venue_road"),
    ("home_away", "receptions", dict(is_home_f=0.0), {}, +0.5,
     "venue_road_neutral"),
]


@pytest.mark.parametrize(
    "group,market,over,medians,impact,expected",
    CASES,
    ids=[f"{c[0]}-{c[5]}-{'up' if c[4] > 0 else 'down'}" for c in CASES],
)
def test_renderer_switches_forms_on_mismatch(group, market, over, medians,
                                             impact, expected):
    out = render_factor(group, _row(**over), market, impact, medians)
    matched = match_templates(out["label"])
    assert expected in matched, (
        f"expected {expected}, label {out['label']!r} matched {matched}")
    assert out["polarity"] == HEADLINE_TEMPLATES[expected].polarity
    # the invariant itself: never assert the opposite of the arrow
    arrow = "up" if impact > 0 else "down"
    assert out["polarity"] in {arrow, "neutral", "contrast"}
    # the registry classifier must round-trip the emitted label
    assert classify_headline(out["label"]) == out["polarity"]


def test_contrast_and_neutral_headlines_carry_the_signed_net():
    out = render_factor(
        "opp_defense",
        _row(opp_allowed_std=177.0, opp_rank_allowed=32.0,
             opp_allowed_l5=210.0, opp_allowed_pos_std=50.0),
        "rec_yds", +13.7, {"opp_allowed_pos_std": 45.0})
    assert "nets out about +14 yds" in out["label"]
    out = render_factor("home_away", _row(is_home_f=0.0), "receptions",
                        +0.43, {})
    assert "nets out about +0.4 catches" in out["label"]


# ---------------------------------------------------------------------------
# the export walk: every shipped factor, both staging and src/data
# ---------------------------------------------------------------------------

def _exported_factors(export_dir: Path):
    for pf in sorted((export_dir / "players").glob("*.json")):
        pj = json.loads(pf.read_text())
        for prop in pj.get("props", []):
            for i, f in enumerate(prop.get("factors", [])):
                yield f"{pf.name} {prop['market']} factor[{i}]", f


@pytest.mark.skipif(not EXPORT_DIRS, reason="no export directory present")
@pytest.mark.parametrize("export_dir", EXPORT_DIRS,
                         ids=[d.name for d in EXPORT_DIRS])
def test_every_exported_headline_agrees_with_its_arrow(export_dir):
    checked = 0
    for where, f in _exported_factors(export_dir):
        assert f["direction"] in {"up", "down"}, where
        polarity = classify_headline(f["label"])
        assert polarity is not None, (
            f"{where}: headline matches no registered template (or several "
            f"with conflicting polarities): {f['label']!r} — matched "
            f"{match_templates(f['label'])}")
        if polarity in {"up", "down"}:
            assert polarity == f["direction"], (
                f"{where}: headline asserts {polarity!r} but the arrow is "
                f"{f['direction']!r} (impact {f['impact']}): {f['label']!r}")
        assert math.isfinite(float(f["impact"])), where
        assert len(f["label"]) <= 140, (
            f"{where}: label runs long ({len(f['label'])} chars): "
            f"{f['label']!r}")
        checked += 1
    assert checked > 0, f"no factors found under {export_dir}"
