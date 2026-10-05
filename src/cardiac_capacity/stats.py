"""Small interval helpers for the v2 recommendation and delta reports (numpy only)."""

from __future__ import annotations

import math

import numpy as np

Z95 = 1.959963984540054
Z99 = 2.5758293035489004


def wilson_interval(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (better than Wald near 0 and 1)."""
    if n < 1:
        raise ValueError("n must be at least 1")
    if not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def mean_ci(values: np.ndarray | list[float], z: float = Z95) -> tuple[float, float, float]:
    """(mean, low, high) with a normal-approximation CI (CLT; use n >= 30)."""
    x = np.asarray(values, dtype=float)
    if x.size < 2:
        raise ValueError("need at least two values")
    m = float(x.mean())
    half = z * float(x.std(ddof=1)) / math.sqrt(x.size)
    return m, m - half, m + half
