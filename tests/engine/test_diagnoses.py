"""The v2.2 diagnosis table, the OR-to-hazard conversion and the diagnosis-driven engine."""

from __future__ import annotations

import math
import random
import re

import pytest

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import diagnoses
from cardiac_capacity.casemix import DelayEffect

NO_CAT_RATES = (0.0, 0.0, 0.0, 0.0)


def _params(mix: diagnoses.Mix, **kw: float) -> cp.PolicyParams:
    return cp.PolicyParams(
        weekly_referrals=kw.pop("weekly_referrals", 6.0),
        deterioration_rates=NO_CAT_RATES,
        casemix=mix.casemix,
        **kw,
    )


def test_table_has_72_cells_and_the_stated_status_counts() -> None:
    assert len(diagnoses.DIAGNOSES) == 12
    assert all(len(d.cells()) == 6 for d in diagnoses.DIAGNOSES)
    assert diagnoses.counts() == {"F": 18, "P": 23, "G": 31}


def test_every_filled_or_proxy_cell_has_a_source_with_a_doi_and_gaps_have_no_value() -> None:
    for d in diagnoses.DIAGNOSES:
        for c in d.cells():
            if c.status == "G":
                assert c.value is None and not c.source, d.key
            else:
                assert "doi:" in c.source, (d.key, c.text)


def test_no_numeric_default_outside_the_table() -> None:
    """With no overrides every number in the mix traces to a table cell."""
    for g in diagnoses.build_mix().casemix.groups:
        if g.key == "hlhs2":
            continue
        d = diagnoses.BY_KEY[g.key]
        assert g.los_days == d.cicu.value
        assert g.share == d.share.value


def test_default_recommendation_leaves_out_gaps_and_says_why() -> None:
    mix = diagnoses.build_mix()
    assert set(mix.included) == {"tof", "tga", "tgavsd", "vsd", "hlhs", "asd", "tapvc"}
    left = dict(mix.excluded)
    for label in ("Complete AVSD", "Coarctation of the aorta", "Other / not listed"):
        assert left[label] == "no CICU stay"


def test_shares_sum_to_one_after_any_edit() -> None:
    rnd = random.Random(1)  # noqa: S311
    for _ in range(50):
        over = {
            d.key: {"share": rnd.random() * 0.3, "cicu": 1.0 + rnd.random() * 10}
            for d in rnd.sample(diagnoses.DIAGNOSES, 5)
        }
        shares = diagnoses.build_mix(over).casemix.arrival_shares()
        assert sum(shares) == pytest.approx(1.0)
        assert min(shares) >= 0


def test_your_figures_include_a_gap_diagnosis_and_are_listed() -> None:
    mix = diagnoses.build_mix({"avsd": {"cicu": 10.0}})
    assert "avsd" in mix.included
    assert any(y.startswith("Complete AVSD") for y in mix.yours)


def test_odds_ratio_to_weekly_hazard_matches_hand_calculation() -> None:
    e = DelayEffect(1.49, 1.02, 2.15, 0.174, 1.0)
    rr = 1.49 / (1 - 0.174 + 0.174 * 1.49)
    assert e.risk_ratio() == pytest.approx(rr)
    assert e.weekly_hazard() == pytest.approx(-math.log(1 - 0.174 * rr))
    assert e.weekly_probability() == pytest.approx(0.174 * rr)  # one-week interval
    lo, mid, hi = e.band()
    assert lo < mid < hi
    four = DelayEffect(1.49, 1.02, 2.15, 0.174, 4.0)  # same risk spread over 4 weeks
    assert (1 - four.weekly_probability()) ** 4 == pytest.approx(1 - 0.174 * rr)


def test_urgency_is_derived_from_the_window_never_entered() -> None:
    got = [diagnoses.urgency_class(w) for w in (0, 1, 4, 5, 13, 26, 31, None)]
    assert got == [1, 1, 1, 2, 2, 3, 4, 4]
    short = diagnoses.build_mix({"tof": {"window": 3.0}}).casemix.groups
    default = diagnoses.build_mix().casemix.groups

    def cls(groups: tuple) -> int:  # type: ignore[type-arg]
        return next(g.cicu_cat for g in groups if g.key == "tof")

    assert cls(short) < cls(default)


def test_shrinking_a_window_never_lowers_the_past_window_count() -> None:
    def past(window: float) -> int:
        mix = diagnoses.build_mix({"tof": {"window": window}})
        i = mix.included.index("tof")
        p = _params(mix)
        return sum(cp.run_metrics(p, 52, s).past_window_by_group[i] for s in range(1, 13))

    assert past(8.0) >= past(26.0) >= past(60.0)


def test_no_default_deterioration_and_a_figure_you_enter_creates_events() -> None:
    mix = diagnoses.build_mix()
    assert all(g.delay is None for g in mix.casemix.groups)
    p = _params(mix, weekly_referrals=20.0, slots=3)
    assert sum(cp.run_metrics(p, 52, s).det_events for s in range(1, 11)) == 0
    mine = _params(
        diagnoses.build_mix({"tgavsd": {"deterioration": 0.3}}), weekly_referrals=20.0, slots=3
    )
    assert sum(cp.run_metrics(mine, 52, s).det_events for s in range(1, 11)) > 0


def test_your_weekly_deterioration_figure_is_used() -> None:
    mix = diagnoses.build_mix({"tof": {"deterioration": 0.2}})
    p = _params(mix, weekly_referrals=15.0, slots=2)
    assert sum(cp.run_metrics(p, 52, s).det_events for s in range(1, 6)) > 0


def test_same_seed_gives_identical_results_over_30_seeds() -> None:
    p = _params(diagnoses.build_mix())
    for s in range(1, 31):
        assert cp.run_metrics(p, 52, s) == cp.run_metrics(p, 52, s)


def test_no_user_visible_category_word_in_table_text() -> None:
    text = diagnoses.table_markdown()
    assert not re.search(r"\bcat(egory)?\s*[1-5]\b|urgency (group|categor)", text, re.I)
