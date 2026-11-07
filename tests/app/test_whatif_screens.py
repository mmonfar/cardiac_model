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
    o = whatif_recommend.Option(1, 6, True, 0.9, 1.0, 40.0, "x")
    d = whatif_recommend.Option(0, 5, False, 0.1, 3.0, 55.0, "y")
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
    assert decision_log.DISCLAIMER in "\n".join(str(m.value) for m in a.markdown)
