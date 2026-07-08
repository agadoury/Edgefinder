"""Local factor attribution rendered as plain-English factors.

Method: group perturbation. For each factor group, the group's features are
replaced with position-conditional training medians and the mean model
re-predicts; the impact is (original - perturbed) in stat units. Groups are
kept when |impact| >= max(1.5% of projection, a small epsilon), sorted by
|impact|, capped at 6 — and the top 3 are always kept so every prop has
something to say. Labels/details are casual sentences with live numbers.
"""

from __future__ import annotations

import math

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


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _rank_phrase(rank: float) -> str:
    """Rank 1 = allows the most. Renders '3rd most' or '5th fewest'."""
    r = int(rank)
    if r == 1:
        return "the most"
    if r == 32:
        return "the fewest"
    if r <= 16:
        return f"{_ordinal(r)} most"
    return f"{_ordinal(33 - r)} fewest"


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


def render_factor(
    group: str, row: pd.Series, market: str, impact: float
) -> dict:
    """Label + detail for one factor group, with live numbers baked in."""
    unit = UNIT_PHRASE[market]
    up = impact > 0
    opp, team = str(row["opp"]), str(row["team"])
    is_yards = market.endswith("_yds")
    amt = abs(impact)
    swing = (f"{_fmt(amt, 0)} yards" if is_yards and amt >= 1
             else f"{_fmt(amt, 1)} {unit}" if market != "pass_tds"
             else f"{_fmt(amt, 2)} touchdown passes")
    nudge = f"nudges the projection {'up' if up else 'down'} by about {swing}"

    if group == "recent_form":
        m3, m8 = row.get("form_mean3"), row.get("form_mean8")
        label = f"Averaging {_fmt(m3)} {unit} over his last 3 games"
        if pd.notna(m8) and pd.notna(m3):
            direction = "up" if m3 >= m8 else "down"
            detail = (f"That's {direction} from {_fmt(m8)} across his last 8; "
                      f"stacked against a typical week at his position, his "
                      f"form {nudge}.")
        else:
            detail = f"Recent production {nudge}."
        return {"label": label, "detail": detail}

    if group == "usage_role":
        if market in ("rec_yds", "receptions"):
            t4 = row.get("elig_targets_m4")
            label = f"Seeing {_fmt(t4)} targets a game over his last 4"
            detail = f"Volume is opportunity — his recent workload {nudge}."
        elif market == "rush_yds":
            t4 = row.get("elig_touches_m4")
            label = f"Getting {_fmt(t4)} touches a game over his last 4"
            detail = f"Carries drive yardage — his recent workload {nudge}."
        else:
            tt = row.get("team_targets_l5")
            label = f"His offense throws about {_fmt(tt, 0)} passes a game"
            detail = f"How often the team drops back {nudge}."
        return {"label": label, "detail": detail}

    if group == "opp_defense":
        allowed = row.get("opp_allowed_std")
        rank = row.get("opp_rank_allowed")
        if pd.notna(allowed) and pd.notna(rank):
            label = (f"{_city(opp)} gives up {_fmt(allowed, 0)} {unit} a game — "
                     f"{_rank_phrase(rank)} in the NFL")
        elif pd.notna(allowed):
            label = f"{_city(opp)} gives up {_fmt(allowed, 0)} {unit} a game"
        else:
            label = f"Not much history yet on {_city(opp)}'s defense"
        # Keep the "generous"/"stingy" framing only when it agrees with the
        # season-long rank quoted in the label; the model also weighs recent
        # defensive form and position-specific splits, which can pull the
        # other way (e.g. a stingy defense overall that leaks to one position).
        generous_by_rank = pd.notna(rank) and int(rank) <= 16
        if pd.isna(rank) or generous_by_rank == up:
            softness = "generous" if up else "stingy"
            detail = f"A matchup this {softness} {nudge}."
        else:
            detail = (f"The season-long numbers lean "
                      f"{'stingy' if up else 'generous'}, but recent defensive "
                      f"form and how they fare against his position count for "
                      f"more here — on balance the matchup {nudge}.")
        return {"label": label, "detail": detail}

    if group == "game_environment":
        total = row.get("vegas_total")
        implied = row.get("team_implied_pts")
        if pd.notna(total) and pd.notna(implied):
            label = (f"Vegas pegs this at {_fmt(total)} total points, "
                     f"about {_fmt(implied, 0)} for the {_nick(team)}")
        else:
            label = "No betting total available for this one"
        detail = f"The expected scoring script {nudge}."
        return {"label": label, "detail": detail}

    if group == "weather":
        if row.get("is_dome") == 1.0:
            label = "Indoor game — weather is a non-factor"
            detail = "Roof's closed, so wind and cold are off the table."
            return {"label": label, "detail": detail}
        wind, temp = row.get("wind_mph"), row.get("temp_f")
        if pd.notna(wind) and wind >= 12:
            label = f"{_fmt(wind, 0)} mph winds in the forecast"
            detail = ("Wind that stiff makes deep throws tough — it "
                      f"{nudge}.")
        elif pd.notna(temp) and temp <= 32:
            label = f"Freezing kickoff — around {_fmt(temp, 0)} degrees"
            detail = f"Cold, heavy air tends to slow scoring; it {nudge}."
        else:
            label = (f"Fair conditions — about {_fmt(temp, 0)} degrees, "
                     f"{_fmt(wind, 0)} mph wind")
            detail = f"Nothing scary in the forecast; weather {nudge}."
        return {"label": label, "detail": detail}

    if group == "rest_schedule":
        if row.get("dnp_last_week") == 1.0:
            label = "Sat out last week"
            detail = f"Coming back from a missed game {nudge}."
        elif (row.get("games_missed_l5") or 0) > 0:
            n = int(row.get("games_missed_l5"))
            label = f"Missed {n} of the last 5 weeks"
            detail = f"The stop-start stretch {nudge}."
        else:
            rest = row.get("rest_days")
            diff = row.get("rest_diff")
            if pd.notna(rest) and rest <= 5:
                label = f"Short week — only {_fmt(rest, 0)} days of rest"
            elif pd.notna(diff) and diff >= 3:
                label = f"Extra rest — {_fmt(rest, 0)} days since his last game"
            elif pd.notna(diff) and diff <= -2 and pd.notna(rest):
                label = (f"Rest edge to {_city(opp)} — {_fmt(rest, 0)} days "
                         f"off vs their {_fmt(rest - diff, 0)}")
            else:
                label = f"Standard rest — {_fmt(rest, 0)} days between games"
            detail = f"The rest edge versus {_city(opp)} {nudge}."
        return {"label": label, "detail": detail}

    if group == "qb_situation":
        starts = row.get("qb_prior_starts")
        if str(row["pos"]) == "QB":
            if pd.notna(starts) and starts <= 3:
                label = f"Only {_fmt(starts, 0)} starts this season — still settling in"
            else:
                label = f"{_fmt(starts, 0)} starts this season under his belt"
            detail = f"How settled the QB job is {nudge}."
        else:
            qb = row.get("qb_name")
            qb_txt = str(qb) if pd.notna(qb) else "his quarterback"
            if pd.notna(starts) and starts <= 3:
                label = (f"{qb_txt} has just {_fmt(starts, 0)} starts this "
                         "season — passing game still unsettled")
            else:
                label = f"{qb_txt} has made {_fmt(starts, 0)} starts this season"
            detail = f"Stability under center {nudge}."
        return {"label": label, "detail": detail}

    # home_away
    if row.get("is_home_f") == 1.0:
        label = "Playing at home"
        detail = f"Home cooking {nudge}."
    else:
        label = f"On the road at {_city(opp)}"
        detail = f"The road trip {nudge}."
    return {"label": label, "detail": detail}


def build_factors(
    row: pd.Series, model: MarketModel, projection: float, market: str
) -> list[dict]:
    """Contract-shaped factor list: 1-6 entries sorted by |impact| desc."""
    impacts = group_impacts(row, model)
    eps = IMPACT_EPS[market]
    threshold = max(0.015 * max(projection, 0.0), eps)
    ranked = sorted(impacts.items(), key=lambda kv: abs(kv[1]), reverse=True)
    chosen = [(g, i) for g, i in ranked if abs(i) >= threshold][:6]
    if len(chosen) < 3:
        chosen = ranked[:3]
    factors = []
    for group, impact in chosen:
        text = render_factor(group, row, market, impact)
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
