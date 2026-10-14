"""The wordmark appears exactly once: Streamlit's logo slot, top left. Never in page content."""

from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / "src" / "cardiac_capacity_planner"


def test_logo_comes_from_the_logo_slot_only():
    ui = (PKG / "ui.py").read_text(encoding="utf-8")
    assert ui.count("st.logo(") == 1
    assert (PKG / "brand" / "wordmark.svg").is_file()


def test_no_wordmark_markup_in_any_view_or_band():
    for py in PKG.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "mm-wordmark" not in text, f"wordmark markup in {py.name}: use ui.sidebar_brand()"
        assert "mmonfar<" not in text, f"hand-written wordmark in {py.name}"


def test_app_calls_sidebar_brand_once():
    app = (PKG / "app.py").read_text(encoding="utf-8")
    assert app.count("ui.sidebar_brand()") == 1


def test_toolbar_is_not_hidden_whole():
    """Hiding stToolbar also hides the logo and the phone's open-sidebar button."""
    ui = (PKG / "ui.py").read_text(encoding="utf-8")
    assert '[data-testid="stToolbar"]' not in ui
