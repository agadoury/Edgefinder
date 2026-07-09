"""M3 metric definitions: pinball, CRPS approximation, Wilson, drift."""

import numpy as np
import pytest

from edgefinder import metrics
from edgefinder.train import QUANTILES


def test_pinball_known_values():
    y = np.array([10.0, 10.0])
    q = np.array([8.0, 12.0])
    # tau=0.5: mean of 0.5*|y-q| = 0.5*2 = 1.0
    assert metrics.pinball_loss(y, q, 0.5) == pytest.approx(1.0)
    # tau=0.9: under-prediction costs tau, over costs (1-tau)
    # row1: 0.9*2 = 1.8 ; row2: 0.1*2 = 0.2 -> mean 1.0
    assert metrics.pinball_loss(y, q, 0.9) == pytest.approx(1.0)
    # asymmetric check with all under-predictions
    assert metrics.pinball_loss(y, np.array([8.0, 8.0]), 0.9) == pytest.approx(1.8)


def test_quantile_table_and_crps():
    rng = np.random.default_rng(3)
    y = rng.normal(50, 10, 4000)
    qmat = np.column_stack([
        np.full(len(y), 50 + 10 * z)
        for z in (-1.645, -1.282, -0.674, 0.0, 0.674, 1.282, 1.645)
    ])
    qt = metrics.quantile_table(y, qmat)
    for tau in QUANTILES:
        key = f"p{int(tau * 100):02d}"
        assert qt[key]["coverage"] == pytest.approx(tau, abs=0.03)
    crps = metrics.crps_approx(qt)
    assert crps == pytest.approx(
        2 * np.mean([v["pinball"] for v in qt.values()]), abs=1e-6)
    assert crps > 0


def test_wilson_interval():
    lo, hi = metrics.wilson_interval(19, 21)
    assert 0 < lo < 19 / 21 < hi <= 1.0
    assert hi - lo > 0.1          # small n => wide interval
    lo_big, hi_big = metrics.wilson_interval(1900, 2100)
    assert hi_big - lo_big < 0.04  # large n => tight
    assert metrics.wilson_interval(0, 0) == (0.0, 1.0)


def test_bucket_drift():
    buckets = [
        {"bucketMid": 0.35, "predicted": 0.36, "actual": 0.30, "n": 100},
        {"bucketMid": 0.55, "predicted": 0.55, "actual": 0.55, "n": 300},
        {"bucketMid": 0.85, "predicted": None, "actual": None, "n": 0},
    ]
    d = metrics.bucket_drift(buckets)
    assert d["worst"] == pytest.approx(0.06)
    assert d["mean"] == pytest.approx(0.06 * 100 / 400)
    assert metrics.bucket_drift([{"predicted": None, "actual": None, "n": 0}]) \
        == {"worst": None, "mean": None}
