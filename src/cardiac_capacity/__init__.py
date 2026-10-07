"""Cardiac surgery capacity simulators behind one ``CapacitySimulator`` protocol.

Two modes of the same planner (CICU is a mode, not a branch):

- ``ward_referral``: stochastic waiting list feeding a surgical ward (v1 and v2 engines).
- ``cicu``: deterministic waiting list constrained by CICU beds (v1 and v2 engines).

``montecarlo`` is the seeded kernel both modes (and later other models) run through.
"""

from cardiac_capacity import (
    casemix,
    cicu,
    cicu_policy,
    cicu_v2,
    montecarlo,
    parameter_sets,
    recommend,
    recommend_cicu,
    risk_groups,
    stats,
    ward_referral,
    ward_referral_v2,
)
from cardiac_capacity.cicu import CicuParams, CicuSimulator
from cardiac_capacity.montecarlo import Distribution, rng, run, summarize, weekly_band
from cardiac_capacity.protocol import CapacitySimulator, monte_carlo
from cardiac_capacity.ward_referral import WardReferralSimulator

__version__ = "2.1.0"

__all__ = [
    "CapacitySimulator",
    "CicuParams",
    "CicuSimulator",
    "Distribution",
    "WardReferralSimulator",
    "casemix",
    "cicu",
    "cicu_policy",
    "cicu_v2",
    "monte_carlo",
    "montecarlo",
    "parameter_sets",
    "recommend",
    "recommend_cicu",
    "risk_groups",
    "rng",
    "stats",
    "run",
    "summarize",
    "ward_referral",
    "ward_referral_v2",
    "weekly_band",
]
