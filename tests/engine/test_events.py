"""What-if events in the engine (station 1): empty events change nothing; each event does what it says."""

from __future__ import annotations

import dataclasses
import json
import pathlib

import pytest

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity.casemix import DEFAULT_CASEMIX

W = 26


def _mean(params: cp.PolicyParams, field: str, n: int = 8) -> float:
    runs = cp.replicate(params, W, n, 500)
    return sum(getattr(r, field) for r in runs) / n


def test_default_events_are_empty() -> None:
    assert cp.PolicyParams().events == ()


def test_empty_events_identical_to_no_events() -> None:
    for base in (cp.PolicyParams(), cp.PolicyParams(casemix=DEFAULT_CASEMIX, occupied_now=(3, 5, 2))):
        for seed in (1, 2, 3):
            assert cp.run_metrics(base, W, seed) == cp.run_metrics(
                dataclasses.replace(base, events=()), W, seed
            )


def test_event_outside_window_changes_nothing() -> None:
    base = cp.PolicyParams()
    late = dataclasses.replace(base, events=(cp.Event("block_beds", 3, start_week=W + 5, duration_weeks=4),))
    assert cp.run_metrics(base, W, 4) == cp.run_metrics(late, W, 4)


def test_old_golden_file_still_present() -> None:
    assert json.loads(pathlib.Path(__file__).parents[1].joinpath("golden", "v21.json").read_text())


def test_block_beds_raises_pressure() -> None:
    base = cp.PolicyParams()
    hit = dataclasses.replace(base, events=(cp.Event("block_beds", 6, start_week=2, duration_weeks=20),))
    assert _mean(hit, "list_end") > _mean(base, "list_end")
    assert _mean(hit, "admissions") < _mean(base, "admissions")


def test_block_all_beds_admits_nobody_in_window() -> None:
    p = cp.PolicyParams(events=(cp.Event("block_beds", 10, start_week=0, duration_weeks=W),))
    assert cp.run_metrics(p, W, 5).admissions == 0


def test_cut_theatre_closed_stops_electives() -> None:
    p = cp.PolicyParams(events=(cp.Event("cut_theatre", 0, start_week=0, duration_weeks=W),))
    frame = cp.run_frame(p, W, 6)
    base = cp.run_frame(cp.PolicyParams(), W, 6)
    assert frame["list"].iloc[-1] > base["list"].iloc[-1]


def test_cut_theatre_never_raises_slots() -> None:
    base = cp.PolicyParams(slots=3)
    p = dataclasses.replace(base, events=(cp.Event("cut_theatre", 5, start_week=0, duration_weeks=W),))
    assert cp.run_metrics(base, W, 7) == cp.run_metrics(p, W, 7)


def test_extra_arrivals_grow_the_list() -> None:
    base = cp.PolicyParams()
    p = dataclasses.replace(base, events=(cp.Event("extra_arrivals", 3, start_week=1, duration_weeks=8),))
    assert _mean(p, "list_end") > _mean(base, "list_end")


def test_extra_arrivals_urgent_category_with_casemix() -> None:
    p = cp.PolicyParams(
        casemix=DEFAULT_CASEMIX,
        events=(cp.Event("extra_arrivals", 3, start_week=1, duration_weeks=4, urgency=1),),
    )
    assert cp.run_metrics(p, W, 8).list_end >= 0


def test_duration_range_is_seeded_and_varies() -> None:
    p = cp.PolicyParams(events=(cp.Event("block_beds", 5, start_week=1, duration_weeks=2, duration_max_weeks=20),))
    assert cp.run_metrics(p, W, 9) == cp.run_metrics(p, W, 9)
    ends = {cp.run_metrics(p, W, s).admissions for s in range(20, 30)}
    assert len(ends) > 1


def test_settled_start_counts_weeks_from_measured_window() -> None:
    p = cp.PolicyParams(
        start_mode="settled", warmup_weeks=10,
        events=(cp.Event("block_beds", 10, start_week=0, duration_weeks=W),),
    )
    assert cp.run_metrics(p, W, 3).admissions == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(kind="meteor", amount=1),
        dict(kind="block_beds", amount=0),
        dict(kind="block_beds", amount=2.5),
        dict(kind="block_beds", amount=-1),
        dict(kind="cut_theatre", amount=-1),
        dict(kind="extra_arrivals", amount=0),
        dict(kind="extra_arrivals", amount=500),
        dict(kind="block_beds", amount=1, start_week=-1),
        dict(kind="block_beds", amount=1, duration_weeks=0),
        dict(kind="block_beds", amount=1, duration_weeks=500),
        dict(kind="block_beds", amount=1, duration_weeks=6, duration_max_weeks=2),
        dict(kind="block_beds", amount=1, urgency=1),
        dict(kind="extra_arrivals", amount=1, urgency=9),
    ],
)
def test_bad_event_refused_with_plain_message(kwargs: dict) -> None:
    with pytest.raises(ValueError) as err:
        cp.Event(**kwargs)
    assert len(str(err.value)) > 10


def test_blocking_more_beds_than_exist_is_refused() -> None:
    p = cp.PolicyParams(beds=6, events=(cp.Event("block_beds", 7),))
    with pytest.raises(ValueError, match="unit has 6"):
        cp.run_metrics(p, 4, 1)
