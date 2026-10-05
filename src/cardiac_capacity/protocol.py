"""The one interface every capacity model implements.

CICU is a *mode* of the capacity planner, not a separate product branch :
the ward-referral model and the CICU model are two implementations of this protocol, and
everything downstream (the Monte Carlo kernel, the planner app) talks to the protocol only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from cardiac_capacity import montecarlo


@runtime_checkable
class CapacitySimulator(Protocol):
    """A weekly capacity simulation with one headline outcome.

    ``simulate`` must be a pure function of its arguments and the model's parameters:
    the same ``(weeks, seed)`` gives the same frame. A deterministic model ignores ``seed``
    and reports ``stochastic = False``.
    """

    @property
    def mode(self) -> str:
        """Short identifier, e.g. ``"ward_referral"`` or ``"cicu"``."""
        ...

    @property
    def stochastic(self) -> bool:
        """Whether ``simulate`` depends on ``seed``."""
        ...

    @property
    def outcome_label(self) -> str:
        """Human label for :meth:`outcome`."""
        ...

    def simulate(self, weeks: int, seed: int | None = None) -> pd.DataFrame:
        """One run: one row per week, with a ``week`` column."""
        ...

    def outcome(self, weekly: pd.DataFrame) -> float:
        """The headline scalar of one run (what the Monte Carlo kernel summarises)."""
        ...


def monte_carlo(
    sim: CapacitySimulator, weeks: int, n: int, seed: int = 0
) -> tuple[list[pd.DataFrame], montecarlo.Distribution]:
    """``n`` seeded runs of ``sim`` and the distribution of its outcome across them."""
    runs = montecarlo.run(lambda s: sim.simulate(weeks, s), n, seed)
    return runs, montecarlo.summarize(sim.outcome(r) for r in runs)
