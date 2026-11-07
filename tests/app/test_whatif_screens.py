"""What-if screens: one question per screen, every button works, disclaimer shown, log saved, no jargon."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from cardiac_capacity import decision_log, whatif_recommend
from cardiac_capacity_planner import whatif_ui as wu

PKG = Path(__file__).resolve().parents[2] / "src" / "cardiac_capacity_planner"
APP = str(PKG / "app.py")
PAGE = "whatif"
LOGPAGE = "whatif-log"
JARGON = re.compile(r"\bcat(egory)?\s*[1-5]\b|\bCI\b|percentile band|hazard|Monte Carlo", re.I)


def _text(at: AppTest) -> str:
    parts = [str(m.value) for m in at.markdown] + [str(c.value) for c in at.caption]
    parts += [str(b.label) for b in at.button] + [str(e.value) for e in at.error]
    return "\n".join(parts)


def _fake_recover(*_a, **_k):
    o = whatif_recommend.Option(1, 6, True, 0.9, 1.0, 40.0, "x", 1.0, 40.0)
    d = whatif_recommend.Option(0, 5, False, 0.1, 3.0, 55.0, "y", 3.0, 55.0)
    return whatif_recommend.Recovery(True, (o,), d, None, None, "Open one extra theatre case a week and the surge bed.")  # type: ignore[arg-type]


@pytest.fixture()
def at(tmp_path, monkeypatch) -> AppTest:
    monkeypatch.setenv("CARDIAC_WHATIF_LOG", str(tmp_path / "log.sqlite"))
    monkeypatch.setattr(whatif_recommend, "recover", _fake_recover)
    a = _open(PAGE)
    assert not a.exception, [e.value for e in a.exception]
    return a


def _open(page: str) -> AppTest:
    a = AppTest.from_file(APP, default_timeout=180)
    a.run()
    a.switch_page(f"views/{page.replace('-', '_')}.py").run()
    return a


def _click(a: AppTest, label: str) -> AppTest:
    [b for b in a.button if b.label == label][0].click().run()
    assert not a.exception, [e.value for e in a.exception]
    return a


def test_first_screen_has_five_cards_and_no_jargon(at: AppTest) -> None:
    labels = [b.label for b in at.button]
    assert labels == ["Beds blocked", "Theatre cut", "Outbreak", "More referrals", "Something else"]
    assert not JARGON.search(_text(at))


def test_whole_flow_runs_and_saves(at: AppTest, tmp_path) -> None:
    _click(at, "Beds blocked")
    assert "Tell me more" in _text(at)
    _click(at, "Next: check")
    assert "3 CICU beds blocked, from week 2, for 2 to 6 weeks." in _text(at)
    _click(at, "Yes, run it")
    text = _text(at)
    assert "Not a medical device" in text and "not a forecast" in text
    assert "Waiting list at the end" in text
    assert not JARGON.search(text)
    _click(at, "What can we do?")
    assert "Open one extra theatre case" in _text(at)
    _click(at, "Record decision")
    _click(at, "Save decision")  # no name yet: refused in plain words
    assert "Please fill in" in _text(at)
    at.text_input[0].set_value("A. Manager")
    at.text_area[0].set_value("Open the surge bed for six weeks.")
    _click(at, "Save decision")
    assert "Saved as consultation number 1" in "\n".join(str(s.value) for s in at.success)
    rows = decision_log.rows(decision_log.open_log(str(tmp_path / "log.sqlite")))
    assert len(rows) == 1 and rows[0]["decision_by"] == "A. Manager"
    _click(at, "Start a new test")
    assert [b.label for b in at.button][0] == "Beds blocked"


def test_every_button_on_every_screen_moves(at: AppTest) -> None:
    for card in ("Theatre cut", "Outbreak", "More referrals", "Something else"):
        a = _open(PAGE)
        _click(a, card)
        assert "Next: check" in [b.label for b in a.button]
        _click(a, "Back")
        assert "Beds blocked" in [b.label for b in a.button]
    _click(at, "Beds blocked")
    _click(at, "Next: check")
    _click(at, "Change")
    assert "Next: check" in [b.label for b in at.button]


def test_sentence_and_events() -> None:
    a = wu.Answers("cut_theatre", 0, 3, 2, 2)
    assert wu.sentence(a) == "Theatre closed, from week 3, for 2 weeks."
    assert wu.make_event(a).amount == 0
    with pytest.raises(ValueError):
        wu.make_event(wu.Answers("block_beds", 3, 0, 6, 2))


def test_past_page_empty_then_filled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CARDIAC_WHATIF_LOG", str(tmp_path / "p.sqlite"))
    a = _open(LOGPAGE)
    assert not a.exception and "Nothing saved yet" in _text(a)
    con = decision_log.open_log(str(tmp_path / "p.sqlite"))
    decision_log.append(con, decision_log.Entry("A", "q", [], "2.2.3", "literature", "500", {}, "keep", "A", "why"))
    a.run()
    assert not a.exception and "One-page print view" in [e.label for e in a.expander]
    # The page footer carries the disclaimer once; the print view is plain words, never raw JSON.
    assert _text(a).count("Not a medical device") == 1
    printed = "\n".join(str(c.value) for c in a.code)
    assert "events_json" not in printed and '{"' not in printed


def _to_screen4(a: AppTest) -> None:
    _click(a, "Beds blocked")
    _click(a, "Next: check")
    _click(a, "Yes, run it")


def test_disclaimer_once_on_screen_4(at: AppTest) -> None:
    _to_screen4(at)
    assert _text(at).count("Not a medical device") == 1


def test_published_source_shown_for_worse_children(at: AppTest) -> None:
    _to_screen4(at)
    assert "doi:10.4103/apc.apc_32_19" in _text(at)
    assert wu.base_params().deterioration_rates[1] > 0  # R023: not the old all-zero placeholder


def _cells(a: AppTest, first: str) -> list[str]:
    """Plain cell texts of the table row whose first cell starts with ``first``."""
    html = " ".join(str(m.value) for m in a.markdown if "<table" in str(m.value))
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if cells and cells[0].startswith(first):
            return cells
    raise AssertionError(first)


def test_same_scenario_same_number_on_screen_4_and_5(tmp_path, monkeypatch) -> None:
    """CEO 7 Nov: a product that contradicts itself is not reliable. Real recovery search, no fake."""
    monkeypatch.setenv("CARDIAC_WHATIF_LOG", str(tmp_path / "log.sqlite"))
    a = _open(PAGE)
    _to_screen4(a)
    list4 = _cells(a, "Waiting list at the end")[2]
    worse4 = _cells(a, "Children who got worse")[2]
    _click(a, "What can we do?")
    keep = _cells(a, "Keep the current plan")
    assert keep[3] == list4 and keep[2] == worse4  # equal, not close
    # Realistic steps: the current 5 cases or at most 3 more, never a jump to 15.
    text = _text(a)
    assert not re.search(r"(?<![0-9])(9|1[0-9]) elective cases", text)
    assert "within 8 elective cases a week" in text or "1. " in text


def test_scenario_object_gives_identical_numbers() -> None:
    sc = wu.scenario_for(wu.Answers("block_beds", 3, 2, 2, 6))
    res = sc.run()
    again = sc.run()
    assert res.get("list_end").scenario.p50 == again.get("list_end").scenario.p50
    rec = sc.recover()
    dn = rec.do_nothing
    assert dn.list_end_p50 == res.get("list_end").scenario.p50
    assert dn.worsen_p50 == res.get("det_events").scenario.p50
    assert (sc.weeks, sc.runs, sc.seed0) == (res.weeks, res.runs, res.seed0)
    # Steps of one case, from the current plan, never past the capacity limit.
    slots = sorted({e.slots for e in rec.recommendation.table})
    assert slots == list(range(wu.SLOTS, wu.SLOTS + whatif_recommend.MAX_EXTRA_CASES + 1))
    if not rec.found:
        assert rec.message.startswith("No safe plan found within 8 elective cases a week")
        assert rec.best_effort is not None and wu.SLOTS <= rec.best_effort.slots <= 8


def test_print_text_has_no_raw_json() -> None:
    row = {
        "id": 1, "utc_time": "t", "asker": "A", "question": "q", "level": "tactical",
        "events_json": '[{"kind": "block_beds", "amount": 3, "start_week": 2, "duration_weeks": 2, "duration_max_weeks": 6, "urgency": null}]',
        "model_version": "2.2.3", "parameter_set": "literature", "seeds": "500 to 529",
        "results_json": '{"weeks": 26, "runs": 30, "measures": [{"measure": "Waiting list at the end", "normal_median": 47.5, "case_median": 54.5, "change_p5": 1, "change_median": 7, "change_p95": 12, "verdict": "worse"}]}',
        "decision_choice": "keep", "decision_by": "A", "decision_why": "w", "review_date": None, "corrects_id": None,
    }  # fmt: skip
    t = wu.print_text(row)
    assert "3 CICU beds blocked, from week 2, for 2 to 6 weeks." in t
    assert "{" not in t and "[" not in t and "Waiting list at the end: normal case 47.5, your case 54.5" in t
