"""Team-code normalization must be schedule-derived and injective."""

import pandas as pd
import pytest

from edgefinder.load import derive_team_map


def _games(rows):
    return pd.DataFrame(rows, columns=["season", "week", "home_team",
                                       "away_team"])


def _hv(rows):
    return pd.DataFrame(rows, columns=["season", "wk", "Team",
                                       "PlayerOpponent"])


def test_alias_resolved_via_schedule():
    games = _games([(2024, 1, "LA", "SEA"), (2024, 1, "KC", "DEN")])
    hv = _hv([
        (2024, 1, "LAR", "@SEA"),   # unknown code, opponent known
        (2024, 1, "SEA", "LAR"),
        (2024, 1, "KC", "DEN"),
        (2024, 1, "DEN", "@KC"),
    ])
    mapping = derive_team_map(hv, games)
    assert mapping["LAR"] == "LA"
    assert mapping["SEA"] == "SEA"


def test_map_is_injective_within_a_season():
    # Two distinct hvpkod codes cannot land on the same nfldata team in
    # one season; here BOTH "LA" and "LAR" appear in 2024 -> error.
    games = _games([(2024, 1, "LA", "SEA"), (2024, 2, "LA", "ARI"),
                    (2024, 2, "SEA", "KC")])
    hv = _hv([
        (2024, 1, "LA", "@SEA"),
        (2024, 1, "SEA", "LA"),
        (2024, 2, "LAR", "ARI"),
        (2024, 2, "ARI", "@LAR"),
    ])
    with pytest.raises(ValueError, match="not injective"):
        derive_team_map(hv, games)


def test_contradicting_schedule_raises():
    games = _games([(2023, 1, "KC", "DEN"), (2023, 1, "LA", "SEA")])
    hv = _hv([(2023, 1, "KC", "SEA")])  # KC actually plays DEN that week
    with pytest.raises(ValueError, match="contradict"):
        derive_team_map(hv, games)
