"""Local factor attribution rendered as plain-English factors.

Method: group perturbation. For each factor group, the group's features are
replaced with position-conditional training medians and the mean model
re-predicts; the impact is (original - perturbed) in stat units. Groups are
kept when |impact| >= max(1.5% of projection, a small epsilon), sorted by
|impact|, capped at 6 — and the top 3 are always kept so every prop has
something to say. Labels/details are casual sentences with live numbers.

Headline polarity (U11). Every headline comes from HEADLINE_TEMPLATES, a
registry in which each template declares the direction its stat framing
implies (up / down / neutral / contrast). Season-long stats and the model's
local attribution — which also weighs recent-form features — can point in
opposite directions; when a group's net impact contradicts the direction
its stat template would assert, the renderer switches to a contrast
headline that leads with the net story and folds the stat in as the
concession ("Season stats say stingy — … — but recent games say beatable;
nets out about +14 yds"). When the group's features genuinely can't
explain the contradiction, it falls back to a neutral headline that
asserts no direction. The registry doubles as a label classifier
(classify_headline) so tests can audit every exported headline against
its arrow without string heuristics.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from edgefinder.features import FACTOR_GROUPS
from edgefinder.train import MarketModel

#: canonical nfldata code -> (city, nickname)
TEAM_NAMES: dict[str, tuple[str, str]] = {
    "ARI": ("Arizona", "Cardinals"), "ATL": ("Atlanta", "Falcons"),
    "BAL": ("Baltimore", "Ravens"), "BUF": ("Buffalo", "Bills"),
    "CAR": ("Carolina", "Panthers"), "CHI": ("Chicago", "Bears"),
    "CIN": ("Cincinnati", "Bengals"), "CLE": ("Cleveland", "Browns"),
    "DAL": ("Dallas", "Cowboys"), "DEN": ("Denver", "Broncos"),
    "DET": ("Detroit", "Lions"), "GB": ("Green Bay", "Packers"),
    "HOU": ("Houston", "Texans"), "IND": ("Indianapolis", "Colts"),
    "JAX": ("Jacksonville", "Jaguars"), "KC": ("Kansas City", "Chiefs"),
    "LA": ("Los Angeles", "Rams"), "LAC": ("Los Angeles", "Chargers"),
    "LV": ("Las Vegas", "Raiders"), "MIA": ("Miami", "Dolphins"),
    "MIN": ("Minnesota", "Vikings"), "NE": ("New England", "Patriots"),
    "NO": ("New Orleans", "Saints"), "NYG": ("New York", "Giants"),
    "NYJ": ("New York", "Jets"), "PHI": ("Philadelphia", "Eagles"),
    "PIT": ("Pittsburgh", "Steelers"), "SEA": ("Seattle", "Seahawks"),
    "SF": ("San Francisco", "49ers"), "TB": ("Tampa Bay", "Buccaneers"),
    "TEN": ("Tennessee", "Titans"), "WAS": ("Washington", "Commanders"),
}

UNIT_PHRASE = {
    "pass_yds": "passing yards", "pass_tds": "touchdown passes",
    "rush_yds": "rushing yards", "rec_yds": "receiving yards",
    "receptions": "catches",
}
IMPACT_EPS = {"pass_yds": 0.5, "rush_yds": 0.5, "rec_yds": 0.5,
              "receptions": 0.05, "pass_tds": 0.03}

# ---------------------------------------------------------------------------
# Headline template registry (U11)
# ---------------------------------------------------------------------------

UP, DOWN, NEUTRAL, CONTRAST = "up", "down", "neutral", "contrast"


@dataclass(frozen=True)
class HeadlineTemplate:
    """A headline format string plus the direction its framing implies.

    polarity is the claim the *text itself* makes: "up"/"down" when the
    stat framing implies a direction for the player, "neutral" when it
    asserts none, "contrast" when it explicitly leads with the net story
    and concedes the stat. Emitted headlines must satisfy
    polarity in {sign(impact), "neutral", "contrast"} — enforced by
    construction in the renderers and audited in pipeline/tests.
    """

    fmt: str
    polarity: str


_T = HeadlineTemplate

HEADLINE_TEMPLATES: dict[str, HeadlineTemplate] = {
    # recent_form -----------------------------------------------------------
    "form_plain": _T("Averaging {m3} {unit} over his last 3 games", NEUTRAL),
    "form_hot": _T("Averaging {m3} {unit} over his last 3 games — up from "
                   "{m8} over his last 8", UP),
    "form_cold": _T("Averaging {m3} {unit} over his last 3 games — down from "
                    "{m8} over his last 8", DOWN),
    "form_contrast_cold": _T("Cooled off — {m3} {unit} over his last 3 — but "
                             "that still beats a typical {pos} week; nets out "
                             "about {net}", CONTRAST),
    "form_contrast_hot": _T("Heating up — {m3} {unit} over his last 3 — but "
                            "still shy of a typical {pos} week; nets out "
                            "about {net}", CONTRAST),
    # usage_role ------------------------------------------------------------
    "usage_heavy": _T("A heavy workload — {stat}", UP),
    "usage_light": _T("A light workload — {stat}", DOWN),
    "usage_targets_plain": _T("Seeing {t} targets a game over his last 4",
                              NEUTRAL),
    "usage_touches_plain": _T("Getting {t} touches a game over his last 4",
                              NEUTRAL),
    "usage_volume_high": _T("His offense airs it out — about {n} passes a "
                            "game", UP),
    "usage_volume_low": _T("A run-leaning offense — about {n} passes a game",
                           DOWN),
    "usage_volume_plain": _T("His offense throws about {n} passes a game",
                             NEUTRAL),
    "usage_contrast_down": _T("Getting plenty of work — {stat} — but his "
                              "broader role reads lighter; nets out about "
                              "{net}", CONTRAST),
    "usage_contrast_up": _T("A modest {stat} — but his broader role is "
                            "bigger than that; nets out about {net}",
                            CONTRAST),
    "usage_neutral": _T("His recent workload is a mixed signal — {stat}; "
                        "nets out about {net}", NEUTRAL),
    # opp_defense -----------------------------------------------------------
    "def_generous": _T("{city} gives up {amt} {unit} a game — {qual} most "
                       "in the NFL", UP),
    "def_stingy": _T("{city} gives up {amt} {unit} a game — {qual} fewest "
                     "in the NFL", DOWN),
    "def_unranked": _T("{city} gives up {amt} {unit} a game", NEUTRAL),
    "def_unknown": _T("Not much history yet on {city}'s defense", NEUTRAL),
    "def_contrast": _T("Season stats say {word} — {concession} — but "
                       "{counter}; nets out about {net}", CONTRAST),
    "def_neutral": _T("{city}'s defense is a mixed picture on {unit} — nets "
                      "out about {net}", NEUTRAL),
    # game_environment ------------------------------------------------------
    "env_high": _T("A high-scoring setup — Vegas pegs this at {total} "
                   "points, about {pts} for the {nick}", UP),
    "env_low": _T("A quiet scoring setup — Vegas pegs this at {total} "
                  "points, about {pts} for the {nick}", DOWN),
    "env_plain": _T("Vegas pegs this at {total} total points, about {pts} "
                    "for the {nick}", NEUTRAL),
    "env_missing": _T("No betting total available for this one", NEUTRAL),
    "env_contrast_down": _T("A big total — {total} points — but only about "
                            "{pts} of them belong to the {nick}; nets out "
                            "about {net}", CONTRAST),
    "env_contrast_up": _T("A modest total — {total} points — but about "
                          "{pts} of it belongs to the {nick}; nets out "
                          "about {net}", CONTRAST),
    "env_neutral": _T("The scoring setup is a mixed signal — {total} total, "
                      "about {pts} for the {nick}; nets out about {net}",
                      NEUTRAL),
    # weather ---------------------------------------------------------------
    "wx_dome": _T("Indoor game — wind and cold are off the table", NEUTRAL),
    "wx_wind": _T("{w} mph winds in the forecast", DOWN),
    "wx_cold": _T("Freezing kickoff — around {t} degrees", DOWN),
    "wx_fair": _T("Fair conditions — about {t} degrees, {w} mph wind",
                  NEUTRAL),
    "wx_contrast_run": _T("{stat} — but rough weather tilts games toward "
                          "the run; nets out about {net}", CONTRAST),
    "wx_neutral": _T("Weather is a wildcard here — {stat}; nets out about "
                     "{net}", NEUTRAL),
    # rest_schedule ---------------------------------------------------------
    # M10: current-week injury-report stories (pre-kickoff info)
    "inj_listed": _T("Listed {status} on this week's injury report", DOWN),
    "inj_listed_neutral": _T("Listed {status} this week — could cut either "
                             "way; nets out about {net}", NEUTRAL),
    "inj_top_out": _T("{n} of his team's top targets ruled out this week — "
                      "more work to go around", UP),
    "inj_top_out_neutral": _T("{n} of his team's top targets ruled out this "
                              "week — shakes up the game plan; nets out "
                              "about {net}", NEUTRAL),
    "rest_dnp": _T("Sat out last week", DOWN),
    "rest_dnp_neutral": _T("Back in after a week off — could cut either "
                           "way; nets out about {net}", NEUTRAL),
    "rest_missed": _T("Missed {n} of the last 5 weeks", DOWN),
    "rest_missed_neutral": _T("A stop-start stretch — missed {n} of the "
                              "last 5 weeks; nets out about {net}", NEUTRAL),
    "rest_short": _T("Short week — only {r} days of rest", DOWN),
    "rest_short_contrast": _T("Short week — {r} days of rest — but "
                              "{opp_city} is working on even less; nets out "
                              "about {net}", CONTRAST),
    "rest_long": _T("Extra rest — {r} days since his last game", UP),
    "rest_edge_opp": _T("Rest edge to {opp_city} — {r} days off vs their "
                        "{r2}", DOWN),
    "rest_standard": _T("Standard rest — {r} days between games", NEUTRAL),
    "rest_neutral": _T("Rest is a mixed factor this week — {r} days between "
                       "games; nets out about {net}", NEUTRAL),
    # qb_situation ----------------------------------------------------------
    "qb_self_new": _T("Only {n} starts this season — still settling in",
                      DOWN),
    "qb_self_vet": _T("{n} starts this season under his belt", NEUTRAL),
    "qb_self_contrast": _T("Only {n} starts this season — but he's "
                           "producing, {y} passing yards a game; nets out "
                           "about {net}", CONTRAST),
    "qb_self_neutral": _T("A newer starter — {n} starts this season; nets "
                          "out about {net}", NEUTRAL),
    "qb_other_new": _T("{qb} has just {n} starts this season — passing game "
                       "still unsettled", DOWN),
    "qb_other_vet": _T("{qb} has made {n} starts this season", NEUTRAL),
    "qb_other_contrast": _T("{qb} has just {n} starts — but he's throwing "
                            "for {y} yards a game in them; nets out about "
                            "{net}", CONTRAST),
    "qb_other_neutral": _T("A newer QB under center — {qb} has {n} starts "
                           "this season; nets out about {net}", NEUTRAL),
    # home_away -------------------------------------------------------------
    "venue_home": _T("Playing at home", UP),
    "venue_home_neutral": _T("Home game this week — nets out about {net}",
                             NEUTRAL),
    "venue_road": _T("On the road at {city}", DOWN),
    "venue_road_neutral": _T("Road game at {city} — nets out about {net}",
                             NEUTRAL),
}


def _template_pattern(fmt: str) -> re.Pattern[str]:
    """Regex matching any instantiation of a template's format string."""
    parts = re.split(r"\{[a-z0-9_]+\}", fmt)
    return re.compile("^" + ".+?".join(re.escape(p) for p in parts) + "$")


_TEMPLATE_PATTERNS: dict[str, re.Pattern[str]] = {
    name: _template_pattern(t.fmt) for name, t in HEADLINE_TEMPLATES.items()
}


def match_templates(label: str) -> list[str]:
    """Names of all templates whose pattern matches the label."""
    return [name for name, pat in _TEMPLATE_PATTERNS.items()
            if pat.fullmatch(label)]


def classify_headline(label: str) -> str | None:
    """Polarity a generated headline asserts, from the template registry.

    Returns None when the label matches no registered template or matches
    templates with conflicting polarities — both are defects the copy
    tests treat as failures.
    """
    polarities = {HEADLINE_TEMPLATES[n].polarity for n in match_templates(label)}
    return polarities.pop() if len(polarities) == 1 else None


def _emit(name: str, **kwargs) -> tuple[str, str]:
    """Instantiate a registered template -> (label, polarity)."""
    t = HEADLINE_TEMPLATES[name]
    return t.fmt.format(**kwargs), t.polarity


def _sign(impact: float) -> str:
    """Direction of the exported arrow ("up" iff impact > 0)."""
    return UP if impact > 0 else DOWN


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _rank_parts(rank: float) -> tuple[str, str]:
    """Rank 1 = allows the most. Returns e.g. ('3rd', 'most'), ('the', 'fewest')."""
    r = int(rank)
    if r == 1:
        return "the", "most"
    if r == 32:
        return "the", "fewest"
    if r <= 16:
        return _ordinal(r), "most"
    return _ordinal(33 - r), "fewest"


def _city(code: str) -> str:
    return TEAM_NAMES.get(code, (code, code))[0]


def _nick(code: str) -> str:
    return TEAM_NAMES.get(code, (code, code))[1]


def _first_name(name: str) -> str:
    return name.split(" ")[0]


def group_impacts(
    row: pd.Series, model: MarketModel
) -> dict[str, float]:
    """Impact per factor group = prediction shift when the group is medianed."""
    feats = model.features
    x0 = pd.DataFrame([row[feats].astype(float)])
    base_pred = float(model.mean_model.predict(x0)[0])
    medians = model.pos_medians.get(str(row["pos"]), model.pos_medians["__all__"])
    impacts: dict[str, float] = {}
    perturbed = []
    groups = list(FACTOR_GROUPS)
    for group in groups:
        xp = x0.copy()
        for col in FACTOR_GROUPS[group]:
            xp.loc[:, col] = medians.get(col, np.nan)
        perturbed.append(xp)
    preds = model.mean_model.predict(pd.concat(perturbed, ignore_index=True))
    for group, pred in zip(groups, preds):
        impacts[group] = base_pred - float(pred)
    return impacts


def _fmt(x: float, dp: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "?"
    if dp == 0:
        return f"{x:,.0f}"
    return f"{x:,.{dp}f}"


def _nudge(impact: float, market: str) -> str:
    """'nudges the projection up by about 12 yards' — for detail lines."""
    unit = UNIT_PHRASE[market]
    is_yards = market.endswith("_yds")
    amt = abs(impact)
    swing = (f"{_fmt(amt, 0)} yards" if is_yards and amt >= 1
             else f"{_fmt(amt, 1)} {unit}" if market != "pass_tds"
             else f"{_fmt(amt, 2)} touchdown passes")
    return f"nudges the projection {'up' if impact > 0 else 'down'} by about {swing}"


def _net(impact: float, market: str) -> str:
    """Signed net phrase for contrast/neutral headlines, e.g. '+14 yds'."""
    if market == "pass_tds":
        return f"{impact:+.2f} TD passes"
    if market == "receptions":
        return f"{impact:+.1f} catches"
    return f"{impact:+.0f} yds" if abs(impact) >= 0.95 else f"{impact:+.1f} yds"


# ---------------------------------------------------------------------------
# Per-group renderers: (label, polarity, detail)
# ---------------------------------------------------------------------------

def _render_recent_form(
    row: pd.Series, market: str, impact: float, medians: dict
) -> tuple[str, str, str]:
    unit = UNIT_PHRASE[market]
    nudge = _nudge(impact, market)
    m3, m8 = row.get("form_mean3"), row.get("form_mean8")
    trend = None
    if pd.notna(m3) and pd.notna(m8):
        band = max(0.08 * abs(m8), 2 * IMPACT_EPS[market])
        if m3 - m8 >= band:
            trend = UP
        elif m8 - m3 >= band:
            trend = DOWN
    if trend is None:
        label, pol = _emit("form_plain", m3=_fmt(m3), unit=unit)
        detail = (f"That's right in line with the {_fmt(m8)} he's averaged "
                  f"across his last 8; against a typical week at his "
                  f"position, his form {nudge}."
                  if pd.notna(m8) else f"Recent production {nudge}.")
        return label, pol, detail
    if trend == _sign(impact):
        name = "form_hot" if trend == UP else "form_cold"
        label, pol = _emit(name, m3=_fmt(m3), unit=unit, m8=_fmt(m8))
        verb = "picked it up" if trend == UP else "cooled off"
        detail = (f"He's {verb} lately — {_fmt(m3)} a game over his last 3 "
                  f"vs {_fmt(m8)} across his last 8; against a typical week "
                  f"at his position, his form {nudge}.")
        return label, pol, detail
    # net impact contradicts the trend framing; the perturbation is measured
    # against a typical week at his position, which explains the difference
    net = _net(impact, market)
    pos = str(row.get("pos"))
    if trend == DOWN:  # cooled off, yet the group still nets positive
        label, pol = _emit("form_contrast_cold", m3=_fmt(m3), unit=unit,
                           pos=pos, net=net)
        detail = (f"He's off the {_fmt(m8)}-a-game pace of his last 8, but "
                  f"{_fmt(m3)} still stacks up above a typical week at his "
                  f"position — on balance his form {nudge}.")
    else:  # heating up, yet the group still nets negative
        label, pol = _emit("form_contrast_hot", m3=_fmt(m3), unit=unit,
                           pos=pos, net=net)
        detail = (f"He's up from {_fmt(m8)} across his last 8, but even the "
                  f"warmer stretch sits below a typical week at his position "
                  f"— on balance his form {nudge}.")
    return label, pol, detail


def _render_usage(
    row: pd.Series, market: str, impact: float, medians: dict
) -> tuple[str, str, str]:
    nudge = _nudge(impact, market)
    net = _net(impact, market)
    if market in ("rec_yds", "receptions"):
        v, med = row.get("elig_targets_m4"), medians.get("targets_m5")
        stat = f"{_fmt(v)} targets a game over his last 4"
        plain = ("usage_targets_plain", {"t": _fmt(v)})
        share_key, team_key = "target_share_l4", "team_targets_l5"
        matched_detail = f"Volume is opportunity — his recent workload {nudge}."
        band = 0.15
    elif market == "rush_yds":
        v, med = row.get("elig_touches_m4"), medians.get("touches_m5")
        stat = f"{_fmt(v)} touches a game over his last 4"
        plain = ("usage_touches_plain", {"t": _fmt(v)})
        share_key, team_key = "touch_share_l4", "team_carries_l5"
        matched_detail = f"Carries drive yardage — his recent workload {nudge}."
        band = 0.15
    else:  # QB volume markets: the visible stat is team passing volume
        v, med = row.get("team_targets_l5"), medians.get("team_targets_l5")
        stat = f"about {_fmt(v, 0)} passes a game"
        plain = ("usage_volume_plain", {"n": _fmt(v, 0)})
        share_key = team_key = None
        matched_detail = f"How often the team drops back {nudge}."
        band = 0.08  # team volumes cluster tightly
    implied = None
    if pd.notna(v) and med is not None and pd.notna(med) and med > 0:
        if v >= med * (1 + band):
            implied = UP
        elif v <= med * (1 - band):
            implied = DOWN
    if implied is None:
        label, pol = _emit(plain[0], **plain[1])
        return label, pol, matched_detail
    if implied == _sign(impact):
        if share_key is None:
            name = "usage_volume_high" if implied == UP else "usage_volume_low"
            label, pol = _emit(name, n=_fmt(v, 0))
        else:
            name = "usage_heavy" if implied == UP else "usage_light"
            label, pol = _emit(name, stat=stat)
        return label, pol, matched_detail
    # mismatch: the quoted count and the group's net impact disagree; the
    # share/team-volume features can carry the counter-story when they agree
    # with the net direction
    if share_key is not None:
        share, share_med = row.get(share_key), medians.get(share_key)
        team, team_med = row.get(team_key), medians.get(team_key)

        def _below(x, m):
            return pd.notna(x) and m is not None and pd.notna(m) and x < m

        def _above(x, m):
            return pd.notna(x) and m is not None and pd.notna(m) and x > m

        if implied == UP and (_below(share, share_med) or _below(team, team_med)):
            label, pol = _emit("usage_contrast_down", stat=stat, net=net)
            detail = (f"The raw counts are strong, but the fuller usage "
                      f"picture — his share of the offense and the team's "
                      f"volume — reads lighter; on balance his workload "
                      f"{nudge}.")
            return label, pol, detail
        if implied == DOWN and (_above(share, share_med) or _above(team, team_med)):
            label, pol = _emit("usage_contrast_up", stat=stat, net=net)
            detail = (f"The raw counts are modest, but the fuller usage "
                      f"picture — his share of the offense and the team's "
                      f"volume — reads stronger; on balance his workload "
                      f"{nudge}.")
            return label, pol, detail
    label, pol = _emit("usage_neutral", stat=stat, net=net)
    detail = (f"The usage signals point in different directions here — on "
              f"balance his workload {nudge}.")
    return label, pol, detail


def _render_defense(
    row: pd.Series, market: str, impact: float, medians: dict
) -> tuple[str, str, str]:
    unit = UNIT_PHRASE[market]
    city = _city(str(row["opp"]))
    nudge = _nudge(impact, market)
    allowed, rank = row.get("opp_allowed_std"), row.get("opp_rank_allowed")
    dp = 1 if market == "pass_tds" else 0
    if pd.isna(allowed):
        label, pol = _emit("def_unknown", city=city)
        return label, pol, f"What they've shown so far {nudge}."
    if pd.isna(rank):
        label, pol = _emit("def_unranked", city=city, amt=_fmt(allowed, dp),
                           unit=unit)
        return label, pol, f"On balance the matchup {nudge}."
    qual, word = _rank_parts(rank)
    implied = UP if word == "most" else DOWN  # 'most allowed' = generous
    if implied == _sign(impact):
        name = "def_generous" if implied == UP else "def_stingy"
        label, pol = _emit(name, city=city, amt=_fmt(allowed, dp), unit=unit,
                           qual=qual)
        softness = "generous" if implied == UP else "stingy"
        return label, pol, f"A matchup this {softness} {nudge}."
    # mismatch: the model also weighs recent defensive form (opp_allowed_l5)
    # and the positional split (opp_allowed_pos_std), which can outweigh the
    # season-long rank the headline would quote
    net = _net(impact, market)
    pos = str(row.get("pos"))
    l5 = row.get("opp_allowed_l5")
    pos_std, pos_med = row.get("opp_allowed_pos_std"), medians.get("opp_allowed_pos_std")
    concession = f"{qual} {word} {unit} allowed"
    recent_leaky = pd.notna(l5) and l5 > allowed * 1.03
    recent_tight = pd.notna(l5) and l5 < allowed * 0.97
    pos_soft = (pd.notna(pos_std) and pos_med is not None
                and pd.notna(pos_med) and pos_std > pos_med)
    pos_tough = (pd.notna(pos_std) and pos_med is not None
                 and pd.notna(pos_med) and pos_std < pos_med)
    if implied == DOWN:  # stingy on the season, but the net impact is up
        if recent_leaky:
            label, pol = _emit("def_contrast", word="stingy",
                               concession=concession,
                               counter="recent games say beatable", net=net)
            detail = (f"{city} has allowed {_fmt(l5, dp)} {unit} a game over "
                      f"its last 5 — leakier than its season-long "
                      f"{_fmt(allowed, dp)} — and recent form counts for "
                      f"more here; on balance the matchup {nudge}.")
        elif pos_soft:
            label, pol = _emit("def_contrast", word="stingy",
                               concession=concession,
                               counter=f"they've been softer against {pos}s",
                               net=net)
            detail = (f"{city} is stingy overall but gives up more than most "
                      f"to {pos}s, and the positional matchup counts for "
                      f"more here — on balance it {nudge}.")
        else:
            label, pol = _emit("def_neutral", city=city, unit=unit, net=net)
            detail = (f"Season-long they allow {_fmt(allowed, dp)} a game "
                      f"({qual} {word} in the NFL), but the fuller matchup "
                      f"read pulls the other way — on balance it {nudge}.")
    else:  # generous on the season, but the net impact is down
        if recent_tight:
            label, pol = _emit("def_contrast", word="generous",
                               concession=concession,
                               counter="they've tightened up lately", net=net)
            detail = (f"{city} has allowed just {_fmt(l5, dp)} {unit} a game "
                      f"over its last 5 — tighter than its season-long "
                      f"{_fmt(allowed, dp)} — and recent form counts for "
                      f"more here; on balance the matchup {nudge}.")
        elif pos_tough:
            label, pol = _emit("def_contrast", word="generous",
                               concession=concession,
                               counter=f"they clamp down on {pos}s", net=net)
            detail = (f"{city} is generous overall but has held {pos}s below "
                      f"the norm, and the positional matchup counts for more "
                      f"here — on balance it {nudge}.")
        else:
            label, pol = _emit("def_neutral", city=city, unit=unit, net=net)
            detail = (f"Season-long they allow {_fmt(allowed, dp)} a game "
                      f"({qual} {word} in the NFL), but the fuller matchup "
                      f"read pulls the other way — on balance it {nudge}.")
    return label, pol, detail


def _render_environment(
    row: pd.Series, market: str, impact: float, medians: dict
) -> tuple[str, str, str]:
    nick = _nick(str(row["team"]))
    nudge = _nudge(impact, market)
    total, pts = row.get("vegas_total"), row.get("team_implied_pts")
    if pd.isna(total) or pd.isna(pts):
        label, pol = _emit("env_missing")
        return label, pol, f"The expected scoring script {nudge}."
    med = medians.get("vegas_total")
    implied = None
    if med is not None and pd.notna(med):
        if total >= med + 2.5:
            implied = UP
        elif total <= med - 2.5:
            implied = DOWN
    if implied is None:
        label, pol = _emit("env_plain", total=_fmt(total), pts=_fmt(pts, 0),
                           nick=nick)
        return label, pol, f"The expected scoring script {nudge}."
    if implied == _sign(impact):
        name = "env_high" if implied == UP else "env_low"
        label, pol = _emit(name, total=_fmt(total), pts=_fmt(pts, 0),
                           nick=nick)
        return label, pol, f"The expected scoring script {nudge}."
    # mismatch: the team's implied share of the total can carry the story
    net = _net(impact, market)
    if implied == UP and pts < total / 2 - 0.5:
        label, pol = _emit("env_contrast_down", total=_fmt(total),
                           pts=_fmt(pts, 0), nick=nick, net=net)
        detail = (f"The total is big, but the {nick} are the underdog side "
                  f"of it — the expected split {nudge}.")
    elif implied == DOWN and pts > total / 2 + 0.5:
        label, pol = _emit("env_contrast_up", total=_fmt(total),
                           pts=_fmt(pts, 0), nick=nick, net=net)
        detail = (f"The total is modest, but the {nick} are expected to do "
                  f"most of the scoring — the expected split {nudge}.")
    else:
        label, pol = _emit("env_neutral", total=_fmt(total), pts=_fmt(pts, 0),
                           nick=nick, net=net)
        detail = (f"The scoring signals cut both ways here — on balance the "
                  f"game script {nudge}.")
    return label, pol, detail


def _render_weather(
    row: pd.Series, market: str, impact: float
) -> tuple[str, str, str]:
    nudge = _nudge(impact, market)
    net = _net(impact, market)
    if row.get("is_dome") == 1.0:
        label, pol = _emit("wx_dome")
        return label, pol, "Roof's closed, so wind and cold are off the table."
    wind, temp = row.get("wind_mph"), row.get("temp_f")
    if pd.notna(wind) and wind >= 12:
        if impact > 0:  # rough-weather framing implies down
            if market == "rush_yds":
                label, pol = _emit("wx_contrast_run",
                                   stat=f"Winds near {_fmt(wind, 0)} mph",
                                   net=net)
                detail = (f"Bad weather usually means more handoffs — the "
                          f"forecast {nudge}.")
            else:
                label, pol = _emit(
                    "wx_neutral",
                    stat=f"{_fmt(wind, 0)} mph wind in the forecast", net=net)
                detail = (f"Wind usually drags on {UNIT_PHRASE[market]}, but "
                          f"it isn't the whole story here — on balance the "
                          f"forecast {nudge}.")
        else:
            label, pol = _emit("wx_wind", w=_fmt(wind, 0))
            detail = f"Wind that stiff makes deep throws tough — it {nudge}."
        return label, pol, detail
    if pd.notna(temp) and temp <= 32:
        if impact > 0:
            if market == "rush_yds":
                label, pol = _emit("wx_contrast_run", stat="A freezing kickoff",
                                   net=net)
                detail = f"Cold games lean on the ground game — the forecast {nudge}."
            else:
                label, pol = _emit(
                    "wx_neutral",
                    stat=f"a freezing kickoff around {_fmt(temp, 0)} degrees",
                    net=net)
                detail = (f"Cold usually slows scoring, but it isn't the "
                          f"whole story here — on balance the forecast "
                          f"{nudge}.")
        else:
            label, pol = _emit("wx_cold", t=_fmt(temp, 0))
            detail = f"Cold, heavy air tends to slow scoring; it {nudge}."
        return label, pol, detail
    label, pol = _emit("wx_fair", t=_fmt(temp, 0), w=_fmt(wind, 0))
    return label, pol, f"Nothing scary in the forecast; weather {nudge}."


def _render_rest(
    row: pd.Series, market: str, impact: float
) -> tuple[str, str, str]:
    opp_city = _city(str(row["opp"]))
    nudge = _nudge(impact, market)
    net = _net(impact, market)
    up = impact > 0
    rest, diff = row.get("rest_days"), row.get("rest_diff")

    # M10: the current week's injury report outranks schedule stories.
    # Emitted-by-construction polarity: the "listed" framing implies down,
    # the teammates-out framing implies up; each flips to its neutral
    # variant when the group's net impact contradicts the framing.
    if row.get("inj_doubtful") == 1.0 or row.get("inj_questionable") == 1.0:
        status = "Doubtful" if row.get("inj_doubtful") == 1.0 else "Questionable"
        practice = ("he didn't practice" if row.get("practice_dnp") == 1.0
                    else "he was limited in practice"
                    if row.get("practice_limited") == 1.0
                    else "practice participation was normal")
        if up:
            label, pol = _emit("inj_listed_neutral", status=status, net=net)
            detail = (f"{status} tag this week ({practice}) — the rest of "
                      f"his profile carries it; on balance the situation "
                      f"{nudge}.")
        else:
            label, pol = _emit("inj_listed", status=status)
            detail = f"The {status} tag ({practice}) {nudge}."
        return label, pol, detail
    top_out = row.get("top3_targets_out")
    if pd.notna(top_out) and top_out >= 1.0:
        n = int(top_out)
        if up:
            label, pol = _emit("inj_top_out", n=n)
            detail = (f"Vacated targets have to land somewhere — the "
                      f"redistribution {nudge}.")
        else:
            label, pol = _emit("inj_top_out_neutral", n=n, net=net)
            detail = (f"Losing a top target shuffles the whole plan — on "
                      f"balance it {nudge}.")
        return label, pol, detail

    if row.get("dnp_last_week") == 1.0:
        if up:  # missed-game framing implies down; nothing here explains up
            label, pol = _emit("rest_dnp_neutral", net=net)
            detail = (f"Layoffs can mean rust or fresh legs; on balance the "
                      f"week off {nudge}.")
        else:
            label, pol = _emit("rest_dnp")
            detail = f"Coming back from a missed game {nudge}."
        return label, pol, detail
    if (row.get("games_missed_l5") or 0) > 0:
        n = int(row.get("games_missed_l5"))
        if up:
            label, pol = _emit("rest_missed_neutral", n=n, net=net)
            detail = (f"Missed time can mean rust or fresh legs; on balance "
                      f"it {nudge}.")
        else:
            label, pol = _emit("rest_missed", n=n)
            detail = f"The stop-start stretch {nudge}."
        return label, pol, detail
    if pd.notna(rest) and rest <= 5:
        if up:
            if pd.notna(diff) and diff > 0:  # opponent is even more squeezed
                label, pol = _emit("rest_short_contrast", r=_fmt(rest, 0),
                                   opp_city=opp_city, net=net)
                detail = (f"Both teams are squeezed, but {opp_city} has even "
                          f"less time to recover — on balance the rest edge "
                          f"{nudge}.")
            else:
                label, pol = _emit("rest_neutral", r=_fmt(rest, 0), net=net)
                detail = (f"The schedule angles cut both ways; on balance "
                          f"rest {nudge}.")
        else:
            label, pol = _emit("rest_short", r=_fmt(rest, 0))
            detail = f"The rest edge versus {opp_city} {nudge}."
        return label, pol, detail
    if pd.notna(diff) and diff >= 3:
        if up:
            label, pol = _emit("rest_long", r=_fmt(rest, 0))
            detail = f"The rest edge versus {opp_city} {nudge}."
        else:  # extra-rest framing implies up; nothing here explains down
            label, pol = _emit("rest_neutral", r=_fmt(rest, 0), net=net)
            detail = (f"The schedule angles cut both ways; on balance rest "
                      f"{nudge}.")
        return label, pol, detail
    if pd.notna(diff) and diff <= -2 and pd.notna(rest):
        if up:
            label, pol = _emit("rest_neutral", r=_fmt(rest, 0), net=net)
            detail = (f"The schedule angles cut both ways; on balance rest "
                      f"{nudge}.")
        else:
            label, pol = _emit("rest_edge_opp", opp_city=opp_city,
                               r=_fmt(rest, 0), r2=_fmt(rest - diff, 0))
            detail = f"The rest edge versus {opp_city} {nudge}."
        return label, pol, detail
    label, pol = _emit("rest_standard", r=_fmt(rest, 0))
    return label, pol, f"The rest edge versus {opp_city} {nudge}."


def _render_qb(
    row: pd.Series, market: str, impact: float, medians: dict
) -> tuple[str, str, str]:
    nudge = _nudge(impact, market)
    net = _net(impact, market)
    starts = row.get("qb_prior_starts")
    is_qb = str(row["pos"]) == "QB"
    qb = row.get("qb_name")
    qb_txt = str(qb) if pd.notna(qb) else "his quarterback"
    if not (pd.notna(starts) and starts <= 3):  # settled situation
        if is_qb:
            label, pol = _emit("qb_self_vet", n=_fmt(starts, 0))
            detail = f"How settled the QB job is {nudge}."
        else:
            label, pol = _emit("qb_other_vet", qb=qb_txt, n=_fmt(starts, 0))
            detail = f"Stability under center {nudge}."
        return label, pol, detail
    n = _fmt(starts, 0)
    if impact <= 0:  # few-starts framing implies down: matched
        if is_qb:
            label, pol = _emit("qb_self_new", n=n)
            detail = f"How settled the QB job is {nudge}."
        else:
            label, pol = _emit("qb_other_new", qb=qb_txt, n=n)
            detail = f"Stability under center {nudge}."
        return label, pol, detail
    # few starts but the group nets positive: production in those starts
    # (qb_pass_yds_l5) can carry the story
    y, y_med = row.get("qb_pass_yds_l5"), medians.get("qb_pass_yds_l5")
    if pd.notna(y) and y_med is not None and pd.notna(y_med) and y > y_med:
        if is_qb:
            label, pol = _emit("qb_self_contrast", n=n, y=_fmt(y, 0), net=net)
        else:
            label, pol = _emit("qb_other_contrast", qb=qb_txt, n=n,
                               y=_fmt(y, 0), net=net)
        detail = (f"Few starts usually means uncertainty, but the passing "
                  f"production in them has been strong — on balance the QB "
                  f"situation {nudge}.")
    else:
        if is_qb:
            label, pol = _emit("qb_self_neutral", n=n, net=net)
        else:
            label, pol = _emit("qb_other_neutral", qb=qb_txt, n=n, net=net)
        detail = (f"A short QB track record cuts both ways — on balance the "
                  f"situation under center {nudge}.")
    return label, pol, detail


def _render_venue(
    row: pd.Series, market: str, impact: float
) -> tuple[str, str, str]:
    nudge = _nudge(impact, market)
    net = _net(impact, market)
    city = _city(str(row["opp"]))
    if row.get("is_home_f") == 1.0:
        if impact > 0:
            label, pol = _emit("venue_home")
            detail = f"Home cooking {nudge}."
        else:  # home framing implies up; no feature explains the flip
            label, pol = _emit("venue_home_neutral", net=net)
            detail = (f"Venue is a small piece of the picture — being home "
                      f"{nudge}.")
    else:
        if impact <= 0:
            label, pol = _emit("venue_road", city=city)
            detail = f"The road trip {nudge}."
        else:
            label, pol = _emit("venue_road_neutral", city=city, net=net)
            detail = (f"Venue is a small piece of the picture — the trip "
                      f"{nudge}.")
    return label, pol, detail


def render_factor(
    group: str, row: pd.Series, market: str, impact: float,
    medians: dict | None = None,
) -> dict:
    """Label + detail (+ headline polarity) for one factor group.

    The label always comes from HEADLINE_TEMPLATES. When the group's net
    impact contradicts the direction its stat framing implies, the copy
    switches to a contrast headline (net story first, stat as concession)
    or, when the group's features can't explain the contradiction, to a
    neutral headline that asserts no direction. ``medians`` are the same
    position-conditional training medians the perturbation uses.
    """
    medians = medians or {}
    if group == "recent_form":
        label, pol, detail = _render_recent_form(row, market, impact, medians)
    elif group == "usage_role":
        label, pol, detail = _render_usage(row, market, impact, medians)
    elif group == "opp_defense":
        label, pol, detail = _render_defense(row, market, impact, medians)
    elif group == "game_environment":
        label, pol, detail = _render_environment(row, market, impact, medians)
    elif group == "weather":
        label, pol, detail = _render_weather(row, market, impact)
    elif group == "rest_schedule":
        label, pol, detail = _render_rest(row, market, impact)
    elif group == "qb_situation":
        label, pol, detail = _render_qb(row, market, impact, medians)
    else:  # home_away
        label, pol, detail = _render_venue(row, market, impact)
    return {"label": label, "detail": detail, "polarity": pol}


def build_factors(
    row: pd.Series, model: MarketModel, projection: float, market: str
) -> list[dict]:
    """Contract-shaped factor list: 1-6 entries sorted by |impact| desc."""
    impacts = group_impacts(row, model)
    medians = model.pos_medians.get(str(row["pos"]), model.pos_medians["__all__"])
    eps = IMPACT_EPS[market]
    threshold = max(0.015 * max(projection, 0.0), eps)
    ranked = sorted(impacts.items(), key=lambda kv: abs(kv[1]), reverse=True)
    chosen = [(g, i) for g, i in ranked if abs(i) >= threshold][:6]
    if len(chosen) < 3:
        chosen = ranked[:3]
    factors = []
    for group, impact in chosen:
        text = render_factor(group, row, market, impact, medians)
        factors.append({
            "group": group,
            "direction": "up" if impact > 0 else "down",
            "impact": round(float(impact), 1 if market.endswith("yds") else 2),
            "label": text["label"],
            "detail": text["detail"],
        })
    return factors


def build_verdict(
    name: str, market: str, projection: float, ref_line: float, over_prob: float
) -> str:
    first = _first_name(name)
    pct = int(round(100 * over_prob))
    side = "clear" if over_prob >= 0.5 else "stay under"
    if market == "pass_tds":
        return (f"The model expects {projection:.1f} touchdown passes — it "
                f"gives {first} a {pct}% chance to go over {ref_line}.")
    if market == "receptions":
        return (f"The model projects {projection:.1f} catches — a {pct}% "
                f"chance to beat a {ref_line}-catch line.")
    unit = UNIT_PHRASE[market]
    return (f"The model projects {projection:.0f} {unit} — it gives {first} "
            f"a {pct}% chance to clear a {ref_line}-yard line.")


def build_confidence_reason(
    confidence: str, games_played: float, rw: float
) -> str:
    gp = int(games_played) if pd.notna(games_played) else 0
    if gp < 5:
        return f"Only {gp} games played this season, so the sample is thin."
    if confidence == "high":
        return f"{gp} games of steady production make this range tight."
    if confidence == "medium":
        return f"Decent {gp}-game sample, but with some week-to-week swing."
    return "His week-to-week range has been wide, so take this one loosely."
