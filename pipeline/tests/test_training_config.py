"""M8 recency weights, M11 log1p quantiles, M12 threshold provenance."""

import json

import numpy as np
import pandas as pd
import pytest

from edgefinder import train
from edgefinder.train import (
    QUANTILES,
    MarketModel,
    load_conf_thresholds,
    recency_weights,
    save_conf_thresholds,
)


# --- M8: recency weights -------------------------------------------------

def test_recency_weights_uniform_when_no_half_life():
    seasons = pd.Series([2021, 2022, 2023, 2024])
    assert (recency_weights(seasons, half_life=None) == 1.0).all()


def test_recency_weights_decay_and_floor():
    seasons = np.array([2021, 2022, 2023, 2024])
    w = recency_weights(seasons, half_life=3.0)
    assert w[-1] == pytest.approx(1.0)            # newest season full weight
    assert w[0] == pytest.approx(0.5)             # 3 seasons back = half
    assert (np.diff(w) > 0).all()                 # strictly newer > older
    # the load-bearing guarantee: early data is down-weighted, never zeroed
    assert (w > 0.05).all()
    # the production half-life keeps 2021 at a real weight
    w_prod = recency_weights(seasons, half_life=train.RECENCY_HALF_LIFE)
    assert (w_prod > 0.05).all()


def test_recency_weights_latest_override_matches_split_fits():
    """h means the same relative decay for 2021-2023 and 2021-2024 fits."""
    w_short = recency_weights(np.array([2021, 2022, 2023]), half_life=2.0)
    w_long = recency_weights(np.array([2021, 2022, 2023, 2024]), half_life=2.0)
    assert w_short[1] / w_short[0] == pytest.approx(w_long[1] / w_long[0])


def test_recency_weights_rejects_nonpositive_half_life():
    with pytest.raises(ValueError):
        recency_weights(np.array([2024]), half_life=0.0)


# --- M11: log1p quantile back-transform ----------------------------------

class _Const:
    def __init__(self, value: float):
        self.value = value

    def predict(self, X):
        return np.full(len(X), self.value)


def test_log1p_quantiles_back_transform():
    """Quantile models fit on log1p(y) must come back on the y scale."""
    log_values = {q: np.log1p(50.0 * q) for q in QUANTILES}  # monotone in q
    model = MarketModel(
        market="rec_yds",
        mean_model=_Const(25.0),
        quantile_models={q: _Const(v) for q, v in log_values.items()},
        features=["f"],
        pos_medians={"__all__": {"f": 0.0}},
        log1p_quantiles=True,
    )
    q = model.predict_quantiles(pd.DataFrame({"f": [0.0]}))
    expected = np.array([50.0 * t for t in QUANTILES])
    assert q[0] == pytest.approx(expected, rel=1e-9)
    assert (np.diff(q[0]) >= 0).all()
    assert (q >= 0).all()


# --- M12: confidence-threshold provenance ---------------------------------

def test_conf_thresholds_roundtrip_with_provenance(tmp_path):
    save_conf_thresholds({"pass_yds": (0.4, 0.6)}, models_dir=tmp_path)
    data = json.loads((tmp_path / "confidence_thresholds.json").read_text())
    assert data["source"] == "2024_walkforward"
    assert data["calSeason"] == 2024
    loaded = load_conf_thresholds(tmp_path)
    assert loaded["pass_yds"] == (0.4, 0.6)


def test_conf_thresholds_rejects_2025_provenance(tmp_path):
    """The circular 2025 fit must be unloadable, not silently accepted."""
    (tmp_path / "confidence_thresholds.json").write_text(json.dumps({
        "source": "2025_backtest",
        "thresholds": {"pass_yds": [0.4, 0.6]},
    }))
    with pytest.raises(ValueError, match="provenance"):
        load_conf_thresholds(tmp_path)


def test_conf_thresholds_rejects_legacy_unstamped_file(tmp_path):
    (tmp_path / "confidence_thresholds.json").write_text(
        json.dumps({"pass_yds": [0.4, 0.6]}))
    with pytest.raises(ValueError, match="provenance"):
        load_conf_thresholds(tmp_path)
