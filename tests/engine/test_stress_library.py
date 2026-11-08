"""Stress-test library (station 6): five presets, separate data, ADEMP text from a real run."""

import pytest

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import stress_library as sl


def test_five_presets_with_unique_keys() -> None:
    assert len(sl.PRESETS) == 5
    assert len({p.key for p in sl.PRESETS}) == 5
    assert all(p.events and p.title and p.story for p in sl.PRESETS)


def test_presets_do_not_change_default_params() -> None:
    assert cp.PolicyParams().events == ()
    assert cp.replicate(cp.PolicyParams(), 12, 3, 500) == cp.replicate(cp.PolicyParams(events=()), 12, 3, 500)


def test_unknown_preset_refused_in_plain_words() -> None:
    with pytest.raises(KeyError, match="No stress test called"):
        sl.get_preset("meteor")


def test_report_has_ademp_ranges_disclaimer_and_run_numbers() -> None:
    p = sl.get_preset("outbreak")
    r = sl.run_preset("outbreak", cp.PolicyParams(), weeks=16, runs=6)
    text = sl.ademp_report(p, r)
    for word in ("Aims:", "Data:", "Estimands:", "Methods:", "Performance:", "not a forecast", "Not a medical device"):
        assert word in text
    m = r.get("list_end")
    assert f"{m.difference.p5:.1f} to {m.difference.p95:.1f}" in text
    assert "forecast:" not in text.lower()


def test_theatre_closed_is_never_better_for_the_list() -> None:
    r = sl.run_preset("theatre_closed", cp.PolicyParams(), weeks=16, runs=6)
    assert r.get("list_end").difference.p50 >= 0
