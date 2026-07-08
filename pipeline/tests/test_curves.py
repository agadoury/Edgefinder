"""Quantile monotonicity + probability-curve invariants."""

import numpy as np

from edgefinder.train import (
    build_prob_curve,
    interp_over,
    lean_of,
    pass_tds_prob_curve,
    strength_of,
    yards_prob_curve,
)


class _FakeQuantileModel:
    def __init__(self, value: float):
        self.value = value

    def predict(self, X):
        return np.full(len(X), self.value)


def test_quantiles_sorted_per_row():
    """Crossing quantile model outputs must come back monotone."""
    from edgefinder.train import QUANTILES, MarketModel

    # deliberately unsorted per-quantile constants
    values = {0.05: 50.0, 0.10: 40.0, 0.25: 90.0, 0.50: 80.0,
              0.75: 120.0, 0.90: 110.0, 0.95: 150.0}
    model = MarketModel(
        market="pass_yds",
        mean_model=_FakeQuantileModel(100.0),
        quantile_models={q: _FakeQuantileModel(values[q]) for q in QUANTILES},
        features=["f"],
        pos_medians={"__all__": {"f": 0.0}},
    )
    import pandas as pd
    q = model.predict_quantiles(pd.DataFrame({"f": [0.0, 1.0]}))
    assert (np.diff(q, axis=1) >= 0).all()
    proj = model.predict_projection(pd.DataFrame({"f": [0.0]}), q[:1])
    assert proj[0] == 0.5 * (100.0 + 90.0)  # p50 after sorting is 90


def test_yards_curve_non_increasing_and_bounded():
    q = np.array([150.0, 178.0, 214.0, 259.0, 301.0, 344.0, 380.0])
    curve = yards_prob_curve(q, 2.5)
    overs = [p["over"] for p in curve]
    lines = [p["line"] for p in curve]
    assert all(a < b for a, b in zip(lines, lines[1:]))
    assert all(a >= b for a, b in zip(overs, overs[1:]))
    assert all(0.0 <= o <= 1.0 for o in overs)
    # median line should be near 50/50
    assert abs(interp_over(curve, 259.0) - 0.5) < 0.03


def test_interp_matches_over_prob_at_ref():
    """The export computes overProbAtRef FROM the curve; re-deriving it via
    the frontend's linear-interp rule must agree exactly."""
    q = np.array([1.0, 2.0, 3.5, 5.0, 6.5, 8.0, 9.0])
    curve = build_prob_curve("receptions", q, 5.0)
    for ref in (2.5, 4.5, 5.5, 7.5):
        stored = interp_over(curve, ref)
        lines = [p["line"] for p in curve]
        overs = [p["over"] for p in curve]
        redo = float(np.interp(ref, lines, overs))
        assert abs(stored - redo) < 1e-9


def test_pass_tds_poisson_curve():
    curve = pass_tds_prob_curve(1.8)
    overs = [p["over"] for p in curve]
    assert [p["line"] for p in curve] == [0.5, 1.5, 2.5, 3.5, 4.5]
    assert all(a >= b for a, b in zip(overs, overs[1:]))
    # P(N > 0) for lambda=1.8 is 1 - e^-1.8 ~ 0.8347
    assert abs(overs[0] - 0.8347) < 0.001


def test_lean_and_strength():
    assert lean_of(0.545) == "over"
    assert lean_of(0.455) == "under"
    assert lean_of(0.52) == "neutral"
    assert strength_of(0.58, "high") == 16
    assert strength_of(0.58, "low") == 11
    assert strength_of(1.0, "high") == 100
