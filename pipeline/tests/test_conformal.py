"""Conformal calibration: 2024-only conformity scores, calibrated bands.

The load-bearing guarantee: conformity scores come from held-out 2024
rows ONLY -- never from 2025, which is the evaluation season. Tested two
ways: directly on calibration_mask, and end-to-end by poisoning 2025
targets and asserting the fitted parameters do not move.
"""

import math
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from edgefinder import conformal
from edgefinder.features import FEATURES
from edgefinder.train import QUANTILES, Q_INDEX


def _frame(rng: np.random.Generator, count: bool = False,
           poison_2025: bool = False) -> pd.DataFrame:
    """Synthetic market frame: seasons 2021-2025, one informative feature."""
    rows_per_season = 260
    seasons = np.repeat([2021, 2022, 2023, 2024, 2025], rows_per_season)
    n = len(seasons)
    signal = rng.uniform(0.0, 10.0, n)
    if count:
        y = rng.poisson(1.0 + 0.5 * signal).astype(float)
    else:
        y = np.clip(30.0 + 8.0 * signal + rng.normal(0, 15, n), 0, None)
    if poison_2025:
        y = np.where(seasons == 2025, 1e6, y)
    frame = pd.DataFrame(0.0, index=range(n), columns=FEATURES)
    frame["form_mean5"] = signal
    frame["season"] = seasons
    frame["week"] = np.tile(np.arange(1, 14), n // 13)
    frame["played"] = True
    frame["eligible"] = True
    frame["prior_played"] = 10.0
    frame["y"] = y
    return frame


def test_calibration_mask_is_2024_only():
    fr = _frame(np.random.default_rng(0))
    fr.loc[0, "played"] = False          # a 2021 row, excluded anyway
    m = conformal.calibration_mask(fr)
    assert m.any()
    assert set(fr.loc[m, "season"].unique()) == {2024}
    assert not m[fr["season"] == 2025].any()

    # played/eligible/prior_played gates apply inside 2024 too
    fr2 = fr.copy()
    is24 = fr2["season"] == 2024
    fr2.loc[is24, "eligible"] = False
    assert not conformal.calibration_mask(fr2).any()


def test_calibration_train_mask_excludes_2024_and_2025():
    fr = _frame(np.random.default_rng(1))
    m = conformal.calibration_train_mask(fr)
    assert set(fr.loc[m, "season"].unique()) == {2021, 2022, 2023}


def test_conformity_scores_never_drawn_from_2025(tmp_path):
    """Poisoning every 2025 target must not change the fitted parameters."""
    fr_clean = _frame(np.random.default_rng(7))
    fr_poison = fr_clean.copy()
    fr_poison["y"] = np.where(fr_poison["season"] == 2025, 1e6,
                              fr_poison["y"])
    cnt_clean = _frame(np.random.default_rng(8), count=True)
    cnt_poison = cnt_clean.copy()
    cnt_poison["y"] = np.where(cnt_poison["season"] == 2025, 1e6,
                               cnt_poison["y"])
    models = {
        "pass_yds": SimpleNamespace(train_info={"max_depth": 3}),
        "receptions": SimpleNamespace(train_info={"max_depth": 3}),
    }
    a = conformal.fit_conformal(
        {"pass_yds": fr_clean, "receptions": cnt_clean}, models,
        models_dir=tmp_path / "a")
    b = conformal.fit_conformal(
        {"pass_yds": fr_poison, "receptions": cnt_poison}, models,
        models_dir=tmp_path / "b")
    assert a.markets == b.markets


def _identity_level_map() -> dict:
    grid = [0.0, 0.25, 0.5, 0.75, 1.0]
    return {"raw": grid, "target": grid}


def _count_params(alpha: float = 0.1) -> dict:
    return {"method": "count_nb", "lambdaScale": 1.0, "alpha": alpha,
            "levelMap": _identity_level_map(), "nCal": 100}


def _calib(markets: dict) -> conformal.Calibrator:
    return conformal.Calibrator({"markets": markets})


def test_additive_adjustment_stays_monotone_and_nonnegative():
    deltas = {f"{q:.2f}": d for q, d in zip(
        QUANTILES, [-30.0, -10.0, -13.0, -8.0, 4.0, 19.0, 27.0])}
    calib = _calib({"pass_yds": {"method": "additive", "deltas": deltas}})
    raw = np.array([[5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0],
                    [150.0, 178.0, 214.0, 259.0, 301.0, 344.0, 380.0]])
    adj = calib.quantile_matrix("pass_yds", raw, mean_pred=None)
    assert (adj >= 0).all()
    assert (np.diff(adj, axis=1) >= 0).all()
    # an interior value: 259 + (-8) = 251
    assert adj[1, Q_INDEX[0.50]] == pytest.approx(251.0)


def test_count_low_quantiles_vary_by_player():
    """The review's degenerate p05=p10=0-for-all-rows must be gone."""
    calib = _calib({"receptions": _count_params()})
    lam = np.array([1.5, 4.0, 7.0])
    q = calib.quantile_matrix("receptions", raw_q=None, mean_pred=lam)
    p10 = q[:, Q_INDEX[0.10]]
    assert (np.diff(q, axis=1) >= 0).all() and (q >= 0).all()
    assert p10[2] > p10[1] > 0.0        # varies with expected volume
    assert len(np.unique(p10)) == len(p10)


def test_count_curve_step_structure_and_push_mass():
    """P(over k) == P(over k+0.5): integer lines exclude the push mass."""
    calib = _calib({"receptions": _count_params()})
    curve = calib.prob_curve("receptions", None, 4.0)
    lines = [p["line"] for p in curve]
    overs = [p["over"] for p in curve]
    assert lines[0] == 0.5
    assert all(a < b for a, b in zip(lines, lines[1:]))
    assert all(a >= b for a, b in zip(overs, overs[1:]))
    assert all(0.0 <= o <= 1.0 for o in overs)
    by_line = dict(zip(lines, overs))
    for k in (1.0, 2.0, 3.0):
        assert by_line[k] == by_line[k + 0.5]
    assert by_line[1.5] > by_line[2.0]  # the drop happens crossing integer 2


def test_pass_tds_curve_matches_poisson_with_identity_map():
    calib = _calib({"pass_tds": _count_params(alpha=0.0)})
    curve = calib.prob_curve("pass_tds", None, 1.8)
    assert [p["line"] for p in curve] == [0.5, 1.5, 2.5, 3.5, 4.5]
    overs = [p["over"] for p in curve]
    assert all(a >= b for a, b in zip(overs, overs[1:]))
    # P(N > 0) for lambda=1.8 is 1 - e^-1.8 ~ 0.8347
    assert overs[0] == pytest.approx(1.0 - math.exp(-1.8), abs=1e-3)


def test_level_map_reshapes_curve():
    """A non-identity level map must move P(over) accordingly."""
    p = _count_params(alpha=0.0)
    # map that says the raw CDF understates the true level everywhere
    p["levelMap"] = {"raw": [0.0, 0.4, 1.0], "target": [0.0, 0.5, 1.0]}
    calib = _calib({"pass_tds": p})
    raw = _calib({"pass_tds": _count_params(alpha=0.0)})
    c_adj = calib.prob_curve("pass_tds", None, 1.8)
    c_raw = raw.prob_curve("pass_tds", None, 1.8)
    assert c_adj[0]["over"] < c_raw[0]["over"]


def test_fs_quantile_order_statistics():
    scores = np.arange(1.0, 101.0)          # 1..100
    assert conformal._fs_quantile(scores, 0.90) == 91.0  # ceil(101*.9)=91
    assert conformal._fs_quantile(scores, 0.10) == 10.0  # floor(101*.1)=10
