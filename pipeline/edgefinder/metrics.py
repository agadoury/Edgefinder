"""Distributional evaluation metrics shared by backtest and validation.

Everything here is a pure function of predictions and outcomes so the same
definitions gate both the 2024 validation decisions (validation.py) and the
reported 2025 walk-forward numbers (backtest.py). Includes the M3 roadmap
metrics: per-quantile pinball loss and empirical coverage, a CRPS
approximation from the quantile set, Brier score for P(over), and Wilson
intervals for small-n hit rates.
"""

from __future__ import annotations

import math

import numpy as np

from edgefinder.train import QUANTILES

#: calibration-bucket edges for P(over ref) reliability tables
CAL_EDGES = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0)


def pinball_loss(y: np.ndarray, q: np.ndarray, tau: float) -> float:
    """Mean pinball (quantile) loss of predictions ``q`` at level ``tau``."""
    d = np.asarray(y, dtype=float) - np.asarray(q, dtype=float)
    return float(np.mean(np.maximum(tau * d, (tau - 1.0) * d)))


def quantile_table(y: np.ndarray, qmat: np.ndarray) -> dict[str, dict[str, float]]:
    """Per-quantile pinball loss and empirical coverage P(y <= q_tau).

    ``qmat`` is the (n, 7) matrix in QUANTILES order. Coverage for a
    well-calibrated tau-quantile is tau itself.
    """
    out: dict[str, dict[str, float]] = {}
    y = np.asarray(y, dtype=float)
    for i, tau in enumerate(QUANTILES):
        key = f"p{int(tau * 100):02d}"
        out[key] = {
            "tau": tau,
            "pinball": round(pinball_loss(y, qmat[:, i], tau), 4),
            "coverage": round(float(np.mean(y <= qmat[:, i])), 4),
        }
    return out


def crps_approx(qtable: dict[str, dict[str, float]]) -> float:
    """CRPS approximation from the quantile set: 2 x average pinball loss.

    Exact CRPS is the integral of 2*pinball_tau over tau in [0, 1]; with a
    finite quantile grid the plain average is the standard approximation.
    Comparable across models scored on the same grid (which is all we use
    it for); not comparable to CRPS computed on a different grid.
    """
    return round(2.0 * float(np.mean([v["pinball"] for v in qtable.values()])), 4)


def brier_score(p_over: np.ndarray, went_over: np.ndarray) -> float:
    """Mean squared error of P(over) against the 0/1 outcome."""
    p = np.asarray(p_over, dtype=float)
    o = np.asarray(went_over, dtype=float)
    return float(np.mean((p - o) ** 2))


def wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (95% by default)."""
    if n == 0:
        return (0.0, 1.0)
    phat = hits / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def calibration_buckets(p_over: np.ndarray, went_over: np.ndarray) -> list[dict]:
    """Reliability table over CAL_EDGES buckets (contract shape)."""
    p = np.asarray(p_over, dtype=float)
    o = np.asarray(went_over, dtype=float)
    buckets = []
    for lo, hi in zip(CAL_EDGES[:-1], CAL_EDGES[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1.0 else (p <= hi))
        n = int(m.sum())
        buckets.append({
            "bucketMid": round((lo + hi) / 2, 2),
            "predicted": round(float(p[m].mean()), 3) if n else None,
            "actual": round(float(o[m].mean()), 3) if n else None,
            "n": n,
        })
    return buckets


def bucket_drift(buckets: list[dict]) -> dict[str, float | None]:
    """Worst and n-weighted mean |predicted - actual| over non-empty buckets."""
    pops = [(abs(b["predicted"] - b["actual"]), b["n"])
            for b in buckets if b["n"]]
    if not pops:
        return {"worst": None, "mean": None}
    drifts = np.array([d for d, _ in pops])
    ns = np.array([n for _, n in pops], dtype=float)
    return {
        "worst": round(float(drifts.max()), 4),
        "mean": round(float((drifts * ns).sum() / ns.sum()), 4),
    }
