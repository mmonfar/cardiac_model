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
        assert o.safe and "no worse than the normal case" in o.text
    assert r.options[0].slots == r.recommendation.slots
    assert r.do_nothing.rank == 0


def test_impossible_scenario_says_no_safe_plan() -> None:
    ev = (cp.Event("block_beds", 10, start_week=0, duration_weeks=26),)
    r = wr.recover(params(), ev, weeks=26, **SMALL)
    assert not r.found and r.options == ()
    assert r.message.startswith("No safe plan found within")
    assert r.best_effort is not None and r.do_nothing.slots <= r.best_effort.slots <= r.do_nothing.slots + wr.MAX_EXTRA_CASES
    assert r.best_effort is not None and not r.best_effort.safe
    assert wr.SAFE_MEANING in r.message and "worse than the normal case on" in r.message


def test_events_reach_the_recommender() -> None:
    ev = (cp.Event("block_beds", 10, start_week=0, duration_weeks=26),)
    r = wr.recover(params(), ev, weeks=26, **SMALL)
    assert r.do_nothing.share_ok == 0.0


NORMAL = {"list grew": 0.2, "unit above the occupancy target": 0.0, "a life-threatening case waited for a bed": 1.0}


def test_normal_case_counts_as_safe_even_with_a_check_it_always_fails() -> None:
    assert wr.worse_than_normal(dict(NORMAL), NORMAL) == {}


def test_plan_worse_than_normal_on_any_check_is_not_safe() -> None:
    for k in NORMAL:
        if NORMAL[k] < 1.0:
            plan = dict(NORMAL, **{k: NORMAL[k] + 0.1})
            assert list(wr.worse_than_normal(plan, NORMAL)) == [k]
    better = dict(NORMAL, **{"list grew": 0.0})
    assert wr.worse_than_normal(better, NORMAL) == {}


def test_event_that_changes_nothing_is_safe_for_the_current_plan() -> None:
    """The normal case must find itself safe. Old test (90% of futures meet all) said no in 100% of futures."""
    ev = (cp.Event("extra_arrivals", 1, start_week=40, duration_weeks=3),)  # starts after the 26-week horizon
    r = wr.recover(params(), ev, weeks=26, **SMALL)
    assert r.do_nothing.safe and r.found
    assert wr.SAFE_MEANING in r.message
