"""M13 FanDuel benchmark: closing-line extraction and schedule mapping.

The benchmark is evaluation-only; these tests pin down the two pieces most
likely to silently corrupt it: picking the LAST pre-kickoff snapshot per
prop, and mapping UTC commence times onto the right (season, week).
"""

import pandas as pd

from edgefinder.fanduel_benchmark import (
    BREAK_EVEN_110,
    closing_lines,
    map_props_to_weeks,
)


def _snapshot(snap, commence, line, event="e1", player="Joe Star"):
    return {
        "requested_snapshot_time": snap,
        "commence_time": commence,
        "event_id": event,
        "player": player,
        "market_key": "player_pass_yds",
        "home_team": "Kansas City Chiefs",
        "away_team": "Detroit Lions",
        "line": line,
        "over_price": 1.91,
        "under_price": 1.91,
    }


def test_closing_line_is_last_snapshot_before_kickoff():
    commence = "2025-09-08T00:20:00Z"
    df = pd.DataFrame([
        _snapshot("2025-09-07T12:00:00Z", commence, 245.5),
        _snapshot("2025-09-07T23:45:00Z", commence, 249.5),   # latest valid
        _snapshot("2025-09-08T01:00:00Z", commence, 260.5),   # post-kickoff
    ])
    out = closing_lines(df)
    assert len(out) == 1
    assert out["line"].iloc[0] == 249.5
    assert out["hours_to_kickoff"].iloc[0] > 0


def test_closing_lines_key_is_event_player_market():
    commence = "2025-09-08T00:20:00Z"
    df = pd.DataFrame([
        _snapshot("2025-09-07T12:00:00Z", commence, 245.5, player="A"),
        _snapshot("2025-09-07T12:00:00Z", commence, 230.5, player="B"),
    ])
    assert len(closing_lines(df)) == 2


def test_map_props_to_weeks_uses_eastern_date():
    games = pd.DataFrame({
        "game_id": ["2025_01_DET_KC"],
        "season": [2025],
        "week": [1],
        "gameday": ["2025-09-07"],   # ET date; kickoff 00:20 UTC = 20:20 ET
        "home_team": ["KC"],
        "away_team": ["DET"],
    })
    df = closing_lines(pd.DataFrame([
        _snapshot("2025-09-07T20:00:00Z", "2025-09-08T00:20:00Z", 249.5),
    ]))
    out = map_props_to_weeks(df, games)
    assert len(out) == 1
    assert int(out["season"].iloc[0]) == 2025
    assert int(out["week"].iloc[0]) == 1


def test_unmatched_events_are_dropped_not_guessed():
    games = pd.DataFrame({
        "game_id": ["2025_01_DET_KC"], "season": [2025], "week": [1],
        "gameday": ["2025-10-01"],  # three weeks away from the prop
        "home_team": ["KC"], "away_team": ["DET"],
    })
    df = closing_lines(pd.DataFrame([
        _snapshot("2025-09-07T20:00:00Z", "2025-09-08T00:20:00Z", 249.5),
    ]))
    assert len(map_props_to_weeks(df, games)) == 0


def test_break_even_constant_is_honest():
    assert abs(BREAK_EVEN_110 - 0.5238) < 0.0001
