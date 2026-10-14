"""v2.2 app: no urgency categories on screen, diagnosis pages, service-only inputs, gap flag."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "src" / "cardiac_capacity_planner" / "app.py"
BANNED = re.compile(r"\bcat(egory)?\s*[1-5]\b|urgency (group|categor)", re.I)


def _text(at: AppTest) -> str:
    parts = [str(m.value) for m in at.markdown] + [str(c.value) for c in at.caption]
    parts += [str(e.label) for e in at.expander] + [str(b.label) for b in at.button]
    parts += [str(n.label) for n in at.number_input] + [str(s.label) for s in at.slider]
    return "\n".join(parts)


def _run(at: AppTest) -> AppTest:
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _fresh() -> AppTest:
    return _run(AppTest.from_file(str(APP), default_timeout=180))


@pytest.fixture(scope="module")
def summary() -> AppTest:
    return _fresh()


def test_no_category_wording_on_any_page(summary: AppTest) -> None:
    assert not BANNED.search(_text(summary))
    for page in ("views/diagnosis.py", "views/assumptions.py"):
        at = _fresh()
        at.switch_page(page)
        assert not BANNED.search(_text(_run(at))), page


def test_summary_names_diagnoses_and_states_what_is_left_out(summary: AppTest) -> None:
    html = _text(summary)
    assert "Left out of this recommendation" in html
    assert "Complete AVSD" in html
    assert "If we do nothing, by diagnosis" in html
    assert "Tetralogy of Fallot" in html
    assert "inputs used here are not from published data" in html


def test_only_service_size_and_staffing_are_free_inputs_on_the_summary(summary: AppTest) -> None:
    assert [n.label for n in summary.number_input] == [
        "Theatre sessions a week (operations)",
        "CICU beds",
        "Children on the waiting list now",
        "New referrals a week",
        "Theatre sessions staff can cover a week",
        "CICU beds nurses can staff",
    ]


def test_by_diagnosis_lists_all_twelve_and_your_figure_flows_to_the_summary() -> None:
    at = _fresh()
    at.switch_page("views/diagnosis.py")
    _run(at)
    assert len(at.expander) == 12
    assert "enter your figures" in _text(at)
    next(n for n in at.number_input if n.key == "in_avsd_cicu").set_value(9.0)
    _run(at)
    at.switch_page("views/summary.py")
    html = _text(_run(at))
    assert "Complete AVSD, Coarctation" not in html  # AVSD is now planned
    assert "Complete AVSD: ciCU stay (days)".lower() in html.lower()  # labelled as yours


def test_reset_button_returns_to_published_figures() -> None:
    at = _fresh()
    at.switch_page("views/diagnosis.py")
    _run(at)
    next(n for n in at.number_input if n.key == "in_avsd_cicu").set_value(9.0)
    _run(at)
    next(b for b in at.button if b.label.startswith("Reset")).click()
    _run(at)
    assert at.session_state["yours"] == {}


def test_assumptions_page_carries_the_counts_and_dois() -> None:
    at = _fresh()
    at.switch_page("views/assumptions.py")
    html = _text(_run(at))
    assert "72 cells" in html and "18 published" in html
    assert html.count("doi:") > 20
