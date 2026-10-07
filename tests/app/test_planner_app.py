"""App-level tests with Streamlit's AppTest: both pages render, are branded, and show the
engine's numbers (computed here independently through ``cardiac_capacity``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from cardiac_capacity import (
    CicuParams,
    CicuSimulator,
    WardReferralSimulator,
    casemix,
    cicu,
    cicu_policy,
    monte_carlo,
    parameter_sets,
    recommend,
    recommend_cicu,
    summarize,
    ward_referral,
)
from cardiac_capacity.ward_referral import DEFAULT_PARAMS
from cardiac_capacity_planner import presentation

W_DEFAULT = {**DEFAULT_PARAMS, **parameter_sets.LITERATURE.ward_params()}

APP = Path(__file__).resolve().parents[2] / "src" / "cardiac_capacity_planner" / "app.py"
CICU_PAGE = "views/cicu.py"
WARD_PAGE = "views/ward.py"


def run(at: AppTest | None = None) -> AppTest:
    at = at or AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def page_html(at: AppTest) -> str:
    return "\n".join(str(m.value) for m in at.markdown)


def ward_run(at: AppTest | None = None) -> AppTest:
    at = run(at)
    at.switch_page(WARD_PAGE)
    return run(at)


def cicu_run(at: AppTest | None = None) -> AppTest:
    at = run(at)
    at.switch_page(CICU_PAGE)
    return run(at)


def slider(at: AppTest, label: str):
    return next(s for s in at.slider if s.label == label)


def number(at: AppTest, label: str):
    return next(n for n in at.number_input if n.label == label)


def ward_expected(
    params: dict, target: int = 26, n: int = 20, seed: int = 0, threshold: float = 0.9,
    start_mode: str = "today",
):  # fmt: skip
    sim = WardReferralSimulator(params, model_version="v2", start_mode=start_mode)
    runs, _ = monte_carlo(sim, 52, n=n, seed=seed)
    at_target = summarize(float(r["Over_26_Wks"].iloc[target]) for r in runs)
    rec = recommend.recommend(
        params, target, threshold, n_select=60, n_validate=200, start_mode=start_mode
    )
    return at_target, rec


def select(at: AppTest, label: str):
    return next(s for s in at.select_slider if s.label == label)


@pytest.fixture(scope="module")
def ward_default() -> AppTest:
    return ward_run()


@pytest.fixture(scope="module")
def cicu_default() -> AppTest:
    return cicu_run()


# ── Ward referral (default page) ────────────────────────────────────────────────────────


def test_ward_is_default_page_with_three_charts(ward_default: AppTest) -> None:
    assert "Detail · ward beds" in page_html(ward_default)
    assert len(ward_default.get("plotly_chart")) == 3


def test_brand_is_applied(ward_default: AppTest) -> None:
    html = page_html(ward_default)
    assert "--mm-teal" in html  # canonical stylesheet injected by the bundled theme
    assert 'class="mm-dot"' in html  # wordmark square, never a typed period


def test_ward_default_numbers_are_the_engines(ward_default: AppTest) -> None:
    at_target, rec = ward_expected(W_DEFAULT)
    html = page_html(ward_default)
    assert presentation.band_text(at_target) in html
    assert f"{rec.slots} operations a week · {rec.beds} beds" in html
    assert "at least 90% of simulated futures" in html
    assert f"<b>{100 * rec.p_validate:.0f}%</b>" in html  # out-of-sample success rate
    assert f"<b>{presentation.breach_status(at_target, 26).label}</b>" in html


def test_ward_v1_comparison_is_off_by_default_and_optional(ward_default: AppTest) -> None:
    assert "Compare with the previous version (v1)" not in page_html(ward_default)
    at = ward_run()
    next(c for c in at.checkbox if c.label == "Show the v1 comparison").set_value(True)
    run(at)
    html = page_html(at)
    assert "Compare with the previous version (v1)" in html
    s1, b1 = ward_referral.find_recommendation(W_DEFAULT, 26)
    assert f"{s1} operations a week · {b1} beds" in html
    runs1, _ = monte_carlo(WardReferralSimulator(W_DEFAULT), 52, n=20, seed=0)
    v1_target = summarize(float(r["Over_26_Wks"].iloc[26]) for r in runs1)
    assert "v1: Waiting more than 26 weeks at week 26" in html
    assert presentation.band_text(v1_target) in html


def test_ward_threshold_is_adjustable() -> None:
    at = ward_run()
    slider(at, "Success threshold (%)").set_value(70)
    run(at)
    _, rec = ward_expected(W_DEFAULT, threshold=0.7)
    html = page_html(at)
    assert "at least 70% of simulated futures" in html
    assert f"{rec.slots} operations a week · {rec.beds} beds" in html


def test_ward_settled_start_mode() -> None:
    at = ward_run()
    at.radio[1].set_value("From a settled state (warm-up first)")
    run(at)
    at_target, rec = ward_expected(W_DEFAULT, start_mode="settled")
    html = page_html(at)
    assert "from a settled state (warm-up first)" in html
    assert presentation.band_text(at_target) in html
    assert f"{rec.slots} operations a week · {rec.beds} beds" in html


def test_ward_your_figures_are_wired_to_the_engine() -> None:
    at = ward_run()
    at.radio[0].set_value("custom")
    run(at)
    for label, v in (
        ("Urgent to life-threatening (% a week)", 12.0),
        ("Semi-urgent to urgent (% a week)", 7.0),
        ("Routine to semi-urgent (% a week)", 4.0),
        ("Stable to routine (% a week; ward model only)", 2.0),
        ("Extra risk after 26 weeks waiting (multiplier)", 1.49),
    ):
        number(at, label).set_value(v)
    run(at)
    params = {**DEFAULT_PARAMS, **parameter_sets.PLACEHOLDERS.ward_params()}
    at_target, rec = ward_expected(params)
    html = page_html(at)
    assert "Your figures" in html
    assert presentation.band_text(at_target) in html
    assert f"{rec.slots} operations a week · {rec.beds} beds" in html


def test_no_ai_or_certainty_wording_in_either_page(
    ward_default: AppTest, cicu_default: AppTest
) -> None:
    for at in (ward_default, cicu_default):
        html = page_html(at)
        assert " AI " not in html and "AI-" not in html and "AI " not in html.replace("MAIN", "")
        assert "certainty" not in html.lower()


@pytest.mark.parametrize(("slots", "beds", "target"), [(10, 16, 20), (2, 4, 30), (6, 12, 12)])
def test_ward_follows_controls(slots: int, beds: int, target: int) -> None:
    at = ward_run()
    slider(at, "Surgery slots / week").set_value(slots)
    slider(at, "Ward beds").set_value(beds)
    slider(at, "Stabilisation goal (week)").set_value(target)
    run(at)
    params = {**W_DEFAULT, "surg_per_week": slots, "total_beds": beds}
    at_target, rec = ward_expected(params, target)
    html = page_html(at)
    assert f"26+ week waits at week {target}" in html
    assert presentation.band_text(at_target) in html
    assert f"{rec.slots} operations a week · {rec.beds} beds" in html
    assert f"<b>{presentation.breach_status(at_target, target).label}</b>" in html


def test_ward_seed_and_runs_change_the_ensemble() -> None:
    at = ward_run()
    number(at, "Base seed").set_value(100)
    select(at, "Runs").set_value(50)
    run(at)
    at_target, _ = ward_expected(W_DEFAULT, n=50, seed=100)
    html = page_html(at)
    assert "50 simulated years" in html
    assert presentation.band_text(at_target) in html


def test_ward_rejects_mix_over_100() -> None:
    at = ward_run()
    slider(at, "Cat 1 (most urgent)").set_value(90)
    run(at)
    assert at.error and "exceeds 100" in at.error[0].value


# ── CICU ────────────────────────────────────────────────────────────────────────────────

DEF = parameter_sets.LITERATURE


def cicu_policy_expected(**kw: object) -> cicu_policy.PolicyParams:
    """The policy the page builds at its defaults (literature rates, 85%, today's list)."""
    mix = [0.05, 0.15, 0.3, 0.5]
    total = sum(mix)
    if total != 1.0:
        mix = [x / total for x in mix]
    base: dict[str, Any] = dict(
        slots=5,
        beds=10,
        target_occupancy=0.85,
        surge_max_los_days=3.0,
        weekly_referrals=5.0,
        initial_backlog=60,
        category_distribution=tuple(mix),
        los_days=(14.0, 10.0, 5.0, 3.0),
        deterioration_rates=DEF.cicu_rates(),
        long_wait_or=DEF.long_wait_or,
        long_wait_weeks=DEF.long_wait_weeks,
        occupied_now=(),
        start_mode="today",
        casemix=None,
    )
    base.update(kw)
    return cicu_policy.PolicyParams(**base)  # type: ignore[arg-type]


def cicu_expected(policy: cicu_policy.PolicyParams, threshold: float = 0.9, n_select: int = 60):
    return recommend_cicu.recommend(
        policy, 52, threshold, n_select=n_select, n_validate=200, n_seed_check=30
    )


def test_cicu_page_renders_five_charts(cicu_default: AppTest) -> None:
    html = page_html(cicu_default)
    assert "Detail · CICU plan" in html
    assert 'class="mm-dot"' in html
    assert len(cicu_default.get("plotly_chart")) == 5


def test_cicu_default_recommendation_is_the_engines(cicu_default: AppTest) -> None:
    policy = cicu_policy_expected()
    rec = cicu_expected(policy)
    html = page_html(cicu_default)
    assert rec.found and rec.check is not None
    assert f"{rec.slots} cases / week" in html
    lo, hi = rec.check.ci
    assert f"<b>{100 * lo:.0f}–{100 * hi:.0f}%</b> (Wilson)" in html
    assert recommend_cicu.plain_words(rec, policy) in html
    assert "Occupancy target 85%" in html
    status = presentation.plan_status(rec, 0.85)
    assert f"<b>{status.label}</b>" in html
    assert "the default is 85%" in html
    ci = rec.surge_assessment.det_diff_ci
    if not rec.surge and ci is not None and ci[1] < 0:
        assert (
            "Optional: your call" in html
        )  # helps, but not needed: the cost is shown, not decided


def test_cicu_deterministic_panel_matches_engine(cicu_default: AppTest) -> None:
    params = CicuParams(deterioration_rates=DEF.cicu_rates())
    sim = CicuSimulator(5, params, model_version="v2")
    summary = sim.summary()
    peak = float(sim.simulate()["cicu_peak_daily"].to_numpy().max())
    recommended = cicu.recommended_capacity(sim.capacity_table())
    html = page_html(cicu_default)
    assert "Older urgent-only test" in html
    assert f"{recommended} / week" in html
    assert f"{peak:.1f}" in html
    assert f"{float(summary['totalCost']):,.0f} cost units" in html


def test_cicu_v1_comparison_is_off_by_default_and_optional(cicu_default: AppTest) -> None:
    assert "Compare with the previous version (v1)" not in page_html(cicu_default)
    at = cicu_run()
    next(c for c in at.checkbox if c.label == "Show the v1 comparison").set_value(True)
    run(at)
    html = page_html(at)
    assert "Compare with the previous version (v1)" in html
    params = CicuParams(deterioration_rates=DEF.cicu_rates())
    v1_peak = float(CicuSimulator(5, params).simulate()["cicu_occupancy"].to_numpy().max())
    assert f"{v1_peak:.1f}" in html
    assert "None in 3–14" in html  # v1 recommended capacity at the default


def test_cicu_occupancy_target_and_threshold_are_adjustable() -> None:
    at = cicu_run()
    slider(at, "Occupancy target (%)").set_value(70)
    slider(at, "Success threshold (%)").set_value(80)
    run(at)
    policy = cicu_policy_expected(target_occupancy=0.70)
    rec = cicu_expected(policy, threshold=0.80)
    html = page_html(at)
    assert "Occupancy target 70%" in html
    assert recommend_cicu.plain_words(rec, policy) in html
    assert "70% full" in html


def test_cicu_surge_bed_is_opened_when_it_is_the_only_way() -> None:
    at = cicu_run()
    number(at, "Weekly referrals").set_value(8)
    run(at)
    policy = cicu_policy_expected(weekly_referrals=8.0)
    rec = cicu_expected(policy)
    html = page_html(at)
    assert rec.found and rec.surge
    assert " + surge bed" in html and "Open it" in html
    assert f"{rec.slots} cases / week" in html


def test_cicu_surge_can_be_switched_off() -> None:
    at = cicu_run()
    number(at, "Weekly referrals").set_value(8)
    next(c for c in at.checkbox if c.label == "Consider an extra (surge) bed").set_value(False)
    run(at)
    html = page_html(at)
    assert "None found" in html  # not feasible without the extra bed
    assert "No plan in the search" in html
    assert "Open it" not in html


def test_cicu_your_figures_can_be_entered() -> None:
    at = cicu_run()
    at.radio[1].set_value("custom")
    run(at)
    for label, v in (
        ("Urgent to life-threatening (% a week)", 5.0),
        ("Semi-urgent to urgent (% a week)", 2.0),
        ("Routine to semi-urgent (% a week)", 1.0),
        ("Extra risk after 26 weeks waiting (multiplier)", 1.49),
    ):
        number(at, label).set_value(v)
    run(at)
    pset = parameter_sets.PLACEHOLDERS
    policy = cicu_policy_expected(
        deterioration_rates=pset.cicu_rates(), long_wait_or=pset.long_wait_or
    )
    rec = cicu_expected(policy)
    html = page_html(at)
    assert "Rates: Your figures" in html
    assert recommend_cicu.plain_words(rec, policy) in html


def test_literature_is_the_default_everywhere(ward_default: AppTest, cicu_default: AppTest) -> None:
    assert ward_default.radio[0].value == "literature"
    assert cicu_default.radio[1].value == "literature"
    assert "Rates: Published literature (default)" in page_html(cicu_default)
    assert parameter_sets.DEFAULT_SET == "literature"


def test_cicu_case_mix_toggle() -> None:
    at = cicu_run()
    next(c for c in at.checkbox if c.label == "Use the lesion case mix").set_value(True)
    run(at)
    shares = tuple(g.share for g in casemix.GROUPS)
    policy = cicu_policy_expected(casemix=casemix.CaseMix(shares=shares))
    rec = cicu_expected(policy)
    assert recommend_cicu.plain_words(rec, policy) in page_html(at)
    assert any(n.label == "TGA (simple) share" for n in at.number_input)


def test_cicu_more_beds_keeps_a_plan_and_inherited_test_passes() -> None:
    at = cicu_run()
    number(at, "CICU beds").set_value(40)
    run(at)
    params = CicuParams(cicu_beds=40, deterioration_rates=DEF.cicu_rates())
    sim = CicuSimulator(5, params, model_version="v2")
    assert cicu.recommended_capacity(sim.capacity_table()) == 3
    html = page_html(at)
    assert "3 / week" in html and "cases / week" in html


@pytest.mark.parametrize(
    ("mode", "rounding"), [("weighted", "ceil"), ("priority", "floor"), ("weighted", "none")]
)
def test_cicu_follows_mode_and_rounding(mode: str, rounding: str) -> None:
    at = cicu_run()
    at.selectbox[0].set_value(mode)
    at.radio[0].set_value(rounding)
    slider(at, "Theatre sessions a week (operations)").set_value(8)
    run(at)
    params = CicuParams(
        rounding_method=rounding, scheduling_mode=mode, deterioration_rates=DEF.cicu_rates()
    )
    summary = CicuSimulator(8, params, model_version="v2").summary()
    html = page_html(at)
    assert f"{float(summary['totalCost']):,.0f} cost units" in html
    assert f"{float(summary['finalBacklog']):g}" in html
