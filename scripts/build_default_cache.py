"""Rebuild data/cache/default_run.json for the default inputs (takes about 1 minute).

Run from the repo root:  PYTHONPATH=src python scripts/build_default_cache.py
Re-run it after any change to the model, the scenarios or the default inputs.
"""

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import diagnoses
from cardiac_capacity_planner import default_cache


def default_base() -> tuple:
    """Same defaults as the sidebar on the Decision summary page."""
    mix = diagnoses.build_mix({})
    base = cp.PolicyParams(
        slots=5, beds=10, target_occupancy=0.85, weekly_referrals=6.0, initial_backlog=60,
        deterioration_rates=(0.0, 0.0, 0.0, 0.0), casemix=mix.casemix,
    )
    return base, 2, 0, 0


if __name__ == "__main__":
    print("wrote", default_cache.write(*default_base()))
