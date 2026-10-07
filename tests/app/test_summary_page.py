"""The decision summary: first screen content, staffing as a constraint, data gaps, sources."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from cardiac_capacity import cicu_policy, evidence, parameter_sets
from cardiac_capacity_planner import scenarios

APP = Path(__file__).resolve().parents[2] / "src" / "cardiac_capacity_planner" / "app.py"


def _html(at: AppTest) -> str:
    return "\n".join(str(m.value) for m in at.markdown)


@pytest.fixture(scope="module")
def summary() -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_first_screen_answers_what_to_do_and_what_if_not(summary: AppTest) -> None:
    html = _html(summary)
    assert "What we need to do" in html
    assert "If we do nothing" in html
    for lever in ("theatre sessions", "CICU beds"):
        assert lever in html
    assert "Staffing" in html
    assert "What the model assumes because data is missing" in html


def test_every_chart_has_a_what_this_means_line(summary: AppTest) -> None:
    html = _html(summary)
    assert len(summary.get("plotly_chart")) == 4
    assert html.count("What this means") >= 4


def test_default_figures_are_the_literature(summary: AppTest) -> None:
    assert summary.radio[0].value == "literature"
    assert "Published literature (default)" in summary.radio[0].options


def test_sources_panel_lists_a_doi_for_every_literature_default() -> None:
    for d in evidence.DEFAULTS:
        if d.basis in ("literature", "proxy"):
            assert "doi:" in d.source, d.name
    assert any("assumption" == d.basis for d in evidence.DEFAULTS)
    assert evidence.gaps()


def test_staffing_cap_blocks_an_option() -> None:
    opts = scenarios.options(5, 10, 2)
    text, ok, ds, db = scenarios.staffing_check(opts[1], staffed_sessions=5, staffed_beds=0)
    assert not ok and ds == 2 and db == 0 and "2 more staffed sessions" in text
    assert scenarios.staffing_check(opts[0], 5, 10)[1]
    assert scenarios.staffing_check(opts[1], 0, 0)[1]  # no cap entered: not limiting


def test_recommendation_prefers_an_option_inside_staffing() -> None:
    base = cicu_policy.PolicyParams(
        weekly_referrals=6.0,
        deterioration_rates=parameter_sets.LITERATURE.cicu_rates(),
        long_wait_or=1.0,
    )
    opts = scenarios.options(5, 10, 2)
    free = [scenarios.evaluate(base, o, 0, 0) for o in opts]
    pick = scenarios.recommend(free)
    assert pick is not None and pick.stops_growth
    assert free[0].list_end > free[0].list_start  # doing nothing lets the list grow
    capped = [scenarios.evaluate(base, o, 5, 10) for o in opts]
    pick2 = scenarios.recommend(capped)
    assert (
        pick2 is None
        or pick2.staffing_ok
        or not any(o.staffing_ok and o.stops_growth for o in capped[1:])
    )
