"""Recovery options (station 4): ranked plans from a run, and an honest 'no safe plan'."""

from typing import Any

import pytest

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import whatif_recommend as wr
from cardiac_capacity.parameter_sets import LITERATURE

SMALL: dict[str, Any] = dict(n_select=30, n_validate=60, n_seed_check=30, max_slots=8)


def params() -> cp.PolicyParams:
    return cp.PolicyParams(deterioration_rates=LITERATURE.cicu_rates())


def test_empty_scenario_refused() -> None:
    with pytest.raises(ValueError, match="at least one event"):
        wr.recover(params(), ())


def test_mild_event_gives_ranked_options_backed_by_runs() -> None:
    ev = (cp.Event("extra_arrivals", 1, start_week=2, duration_weeks=3),)
    r = wr.recover(params(), ev, weeks=26, **SMALL)
    assert r.found and 1 <= len(r.options) <= wr.MAX_OPTIONS
    assert [o.rank for o in r.options] == list(range(1, len(r.options) + 1))
    for o in r.options:
        assert o.share_ok >= r.recommendation.threshold
        assert "simulated futures" in o.text
    assert r.options[0].slots == r.recommendation.slots
    assert r.do_nothing.rank == 0


def test_impossible_scenario_says_no_safe_plan() -> None:
    ev = (cp.Event("block_beds", 10, start_week=0, duration_weeks=26),)
    r = wr.recover(params(), ev, weeks=26, **SMALL)
    assert not r.found and r.options == ()
    assert r.message == wr.NO_PLAN
    assert r.best_effort is not None and r.best_effort.share_ok < r.recommendation.threshold


def test_events_reach_the_recommender() -> None:
    ev = (cp.Event("block_beds", 10, start_week=0, duration_weeks=26),)
    r = wr.recover(params(), ev, weeks=26, **SMALL)
    assert r.do_nothing.share_ok == 0.0
