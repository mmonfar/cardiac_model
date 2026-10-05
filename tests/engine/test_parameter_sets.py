"""Parameter sets and the lesion-to-category map ."""

from __future__ import annotations

import pytest

from cardiac_capacity import (
    casemix,
)
from cardiac_capacity import (
    parameter_sets as ps,
)
from cardiac_capacity import (
    risk_groups as rg,
)
from cardiac_capacity import (
    ward_referral_v2 as w2,
)


def test_placeholders_are_what_v2_shipped() -> None:
    assert ps.PLACEHOLDERS.rates == w2.DET_DEFAULTS
    assert ps.PLACEHOLDERS.long_wait_or == w2.LONG_WAIT_OR_DEFAULT == 1.49
    assert ps.PLACEHOLDERS.cicu_rates() == (0.0, 0.05, 0.02, 0.01)
    assert ps.DEFAULT_SET == "placeholders"  # default unchanged until a clinical check


def test_literature_rates_are_the_sourced_hazards() -> None:
    r = ps.LITERATURE.rates
    assert r[0] == 0.0234  # complete AVSD
    assert r[1] == pytest.approx(
        1 - (1 - 0.0020) * (1 - 0.0103)
    )  # large VSD death or loss of operability
    assert r[2] == 0.0080  # ToF
    assert r[3] == 0.02  # category 5 to 4: awaiting source, placeholder kept
    assert ps.LITERATURE.long_wait_or == 1.0
    assert "awaiting" in ps.LITERATURE.notes
    assert ps.LITERATURE.cicu_rates() == (0.0, r[0], r[1], r[2])


def test_ward_params_feed_v2_keys() -> None:
    p = ps.LITERATURE.ward_params()
    assert set(p) == {*ps.RATE_KEYS, "long_wait_or", "long_wait_weeks"}
    probs = w2.deterioration_probabilities(p)
    assert probs[2] == 0.0234 and probs[4] == 0.0080


def test_unknown_set_is_an_error() -> None:
    with pytest.raises(ValueError, match="unknown parameter set"):
        ps.get("made-up")
    assert ps.get("literature") is ps.LITERATURE


def test_lesion_map_is_complete_and_consistent() -> None:
    m = {x.group: x for x in rg.LESION_MAP}
    assert m["Transposition (TGA, simple)"].ward_cat == 1
    assert m["Hypoplastic left heart (HLHS)"].cicu_cat == 1
    assert m["Complete AVSD"].ward_cat == 2
    assert m["Large VSD"].ward_cat == 3
    assert m["Tetralogy of Fallot (ToF)"].ward_cat == 4
    assert m["Small or moderate VSD and other routine lesions"].ward_cat == 5
    for x in rg.LESION_MAP:
        assert x.basis and x.source and x.status == "awaiting clinical check"
        assert x.cicu_cat == min(x.ward_cat, 4)
    assert len(rg.lesion_map_markdown().strip().splitlines()) == 2 + len(rg.LESION_MAP)


def test_casemix_categories_follow_the_lesion_map() -> None:
    by = {x.group: x.cicu_cat for x in rg.LESION_MAP}
    pairs = {
        "tga": "Transposition (TGA, simple)",
        "tgavsd": "TGA with VSD",
        "hlhs": "Hypoplastic left heart (HLHS)",
        "avsd": "Complete AVSD",
        "vsd": "Large VSD",
        "tof": "Tetralogy of Fallot (ToF)",
    }
    for g in casemix.GROUPS:
        if g.key in pairs:
            assert g.cicu_cat == by[pairs[g.key]]


def test_casemix_shares_normalise_and_report_categories() -> None:
    mix = casemix.DEFAULT_CASEMIX
    assert sum(mix.arrival_shares()) == pytest.approx(1.0)
    cats = mix.category_shares()
    assert sum(cats) == pytest.approx(1.0)
    assert cats[0] == pytest.approx(0.08)
    assert mix.groups[mix.index("hlhs2")].share == 0.0  # planned stage, never a referral
    with pytest.raises(ValueError):
        casemix.CaseMix(shares=(0,) * len(mix.groups)).arrival_shares()
    assert len(casemix.casemix_table_markdown().strip().splitlines()) == 2 + len(mix.groups)
