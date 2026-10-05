"""A small seeded Monte Carlo kernel: one RNG factory, one replication loop, one summary.

Design choices:

- ``rng(seed)`` returns numpy's legacy ``RandomState`` (MT19937), not a ``Generator``.
  ``np.random.seed(s)`` followed by ``np.random.<draw>`` is exactly ``RandomState(s).<draw>``,
  so the ported models reproduce the originals bit for bit, and NEP 19 freezes that stream
  across numpy releases. A new model with no legacy outputs to match may use
  ``np.random.default_rng`` instead; ``run`` does not care.
- ``run(fn, n, seed)`` hands each replication an *integer* seed ``seed + i``, not an RNG
  object. That is what the v1 stress test did (``seed=i for i in range(20)``,
  i.e. ``seed=0``), and it keeps the kernel RNG-agnostic: a model built on the standard
  library's ``random.Random(seed)`` (``staff_planner_app.stochastic``) can adopt it unchanged.
- ``summarize`` reports p5/p50/p95. The default is numpy's ``"linear"`` interpolation;
  ``method="inverted_cdf"`` gives the nearest-rank percentile ``staff_planner_app`` uses.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

import numpy as np
import pandas as pd

T = TypeVar("T")

PERCENTILES = (5, 50, 95)


def rng(seed: int | None = None) -> np.random.RandomState:
    """Independent RNG for one replication. ``None`` draws fresh OS entropy (not reproducible)."""
    return np.random.RandomState(seed)


def run(fn: Callable[[int], T], n: int, seed: int = 0) -> list[T]:
    """Call ``fn(seed + i)`` for ``i`` in ``range(n)``: ``n`` reproducible replications."""
    if n < 1:
        raise ValueError("n must be at least 1")
    return [fn(seed + i) for i in range(n)]


@dataclass(frozen=True)
class Distribution:
    """Summary of a sample of one scalar outcome across replications."""

    n: int
    mean: float
    p5: float
    p50: float
    p95: float
    min: float
    max: float

    @property
    def spread(self) -> float:
        """Width of the central 90 % interval."""
        return self.p95 - self.p5


def summarize(samples: Iterable[float], method: str = "linear") -> Distribution:
    """p5/p50/p95, mean and range of ``samples`` (at least one value)."""
    values = np.asarray(list(samples), dtype=float)
    if values.size == 0:
        raise ValueError("cannot summarise an empty sample")
    p5, p50, p95 = np.percentile(values, PERCENTILES, method=method)  # type: ignore[call-overload]
    return Distribution(
        n=int(values.size),
        mean=float(values.mean()),
        p5=float(p5),
        p50=float(p50),
        p95=float(p95),
        min=float(values.min()),
        max=float(values.max()),
    )


def weekly_band(runs: Iterable[pd.DataFrame], column: str, method: str = "linear") -> pd.DataFrame:
    """Per-week p5/p50/p95 of ``column`` across replications that share a ``week`` column."""
    stacked = pd.concat(
        [r[["week", column]].assign(replication=i) for i, r in enumerate(runs)],
        ignore_index=True,
    )
    wide = stacked.pivot(index="week", columns="replication", values=column).astype(float)
    q = np.percentile(wide.to_numpy(), PERCENTILES, axis=1, method=method)  # type: ignore[call-overload]
    return pd.DataFrame({"week": wide.index, "p5": q[0], "p50": q[1], "p95": q[2]}).reset_index(
        drop=True
    )
