"""CICU recommender v2: objective, surge decision, interval and seed rules."""

from __future__ import annotations

from typing import Any

import pytest

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import recommend_cicu as rc
from cardiac_capacity.parameter_sets import LITERATURE
from cardiac_capacity.stats import wilson_interval

SMALL: dict[str, Any] = dict(n_select=30, n_validate=60, n_seed_check=30, max_slots=10)


def params(**kw: object) -> cp.PolicyParams:
    return cp.PolicyParams(deterioration_rates=LITERATURE.cicu_rates(), **kw)  # type: ignore[arg-type]


def test_run_ok_needs_every_criterion() -> None:
    p = params()
    m = cp.run_metrics(p.with_plan(8, False), 52, 3)
    assert rc.run_ok(m, p.with_plan(8, False)) == (
        m.growth <= 5 and m.mean_occupancy <= 0.85 and m.cat1_unserved_days == 0
    )
    assert rc.growth_tolerance(params(weekly_referrals=0.2)) == 1


def test_default_scenario_is_found_and_reports_the_rules() -> None:
    p = params()
    r = rc.recommend(p, **SMALL)
    assert r.found and r.check is not None and r.seed_check is not None and r.plan is not None
    assert r.check.n == 60 and r.seed_check.n == 30
    assert r.check.ci == wilson_interval(r.check.n_ok, r.check.n)
    # Selection, validation and seed-check seeds are disjoint blocks.
    assert len({rc.SEED_SELECT, rc.SEED_VALIDATE, rc.SEED_CHECK}) == 3
    seeds = {s for s, *_ in r.check.per_seed} & {s for s, *_ in r.seed_check.per_seed}
    assert not seeds
    # Never recommends fewer slots than the minimum that stops the list growing.
    assert r.min_slots_feasible is not None and r.slots is not None
    assert r.slots >= r.min_slots_feasible
    # Without a cost cap the surge bed is not recommended when it is not needed.
    assert not r.surge and not r.surge_assessment.recommended


def test_chosen_plan_meets_the_threshold_on_selection_seeds() -> None:
    r = rc.recommend(params(), **SMALL)
    assert r.plan is not None and r.plan.p_ok >= r.threshold


def test_threshold_is_monotone() -> None:
    p = params(weekly_referrals=6)
    lo = rc.recommend(p, threshold=0.5, **SMALL)
    hi = rc.recommend(p, threshold=0.95, **SMALL)
    assert lo.found and lo.min_slots_feasible is not None
    if hi.found:
        assert hi.min_slots_feasible is not None
        assert hi.min_slots_feasible >= lo.min_slots_feasible


def test_nothing_feasible_says_so_in_plain_words() -> None:
    p = params(beds=4, weekly_referrals=12)
    r = rc.recommend(p, **SMALL)
    assert not r.found and r.best_effort is not None
    text = rc.plain_words(r, p)
    assert text.startswith("No plan in the search")
    assert "85%" in text


def test_surge_bed_recommended_when_it_is_the_only_way() -> None:
    p = params(weekly_referrals=8)  # 10 beds, 8 referrals a week: only feasible with the extra bed
    r = rc.recommend(p, n_select=40, n_validate=60, n_seed_check=30, max_slots=15)
    assert r.found and r.surge and r.surge_assessment.recommended
    assert "only way" in r.surge_assessment.reason or "No plan without" in r.surge_assessment.reason
    assert r.surge_assessment.bed_days_opened == 52 * 7
    text = rc.plain_words(r, p)
    assert "surge" in text and "fresh simulated years" in text


def test_cap_on_cost_per_event_controls_a_discretionary_surge_bed() -> None:
    p = params()
    free = rc.recommend(p, max_bed_days_per_event=1e9, **SMALL)
    stingy = rc.recommend(p, max_bed_days_per_event=1.0, **SMALL)
    assert not stingy.surge
    a = free.surge_assessment
    if a.det_diff_ci is not None and a.det_diff_ci[1] < 0:
        assert free.surge  # significant and under an unlimited cap


def test_early_stopping_does_not_change_a_completed_evaluation() -> None:
    p = params()
    a = rc.evaluate_plan(p, 9, False, 52, 40, 123)
    b = rc.evaluate_plan(p, 9, False, 52, 40, 123, threshold=0.5)
    assert b.complete and (a.n_ok, a.det) == (b.n_ok, b.det)
    c = rc.evaluate_plan(p, 1, False, 52, 40, 123, threshold=0.9)
    assert not c.complete and c.n < 40


def test_seed_check_needs_thirty_seeds() -> None:
    with pytest.raises(ValueError, match="30 seeds"):
        rc.recommend(
            params(), n_seed_check=10, **{k: v for k, v in SMALL.items() if k != "n_seed_check"}
        )
    with pytest.raises(ValueError):
        rc.recommend(params(), threshold=1.0, **SMALL)


def test_stability_runs_blocks_and_wording_has_no_banned_terms() -> None:
    p = params()
    s = rc.stability(p, n_blocks=3, n_select=20, max_slots=8, consider_surge=False)
    assert len(s) == 3 and all(isinstance(x[1], bool) for x in s)
    text = rc.plain_words(rc.recommend(p, **SMALL), p)
    for banned in (" AI ", "certainty"):
        assert banned not in text
