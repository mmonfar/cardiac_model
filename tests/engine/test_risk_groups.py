"""The condition-group risk table: arithmetic and honesty checks."""

from __future__ import annotations

import pytest

from cardiac_capacity import risk_groups as rg


def test_odds_multiplication() -> None:
    assert rg.odds_multiplied(0.2, 1.0) == pytest.approx(0.2)
    # odds 0.25 x 1.49 = 0.3725, probability 0.27141...
    assert rg.odds_multiplied(0.2, 1.49) == pytest.approx(0.3725 / 1.3725)
    assert rg.odds_multiplied(0.0, 1.49) == 0.0


def test_every_row_is_marked_awaiting_check_and_sourced() -> None:
    for g in rg.GROUPS:
        assert g.status == "awaiting clinical check"
        assert g.rate_source and g.published_ratio and g.use


def test_rates_match_the_hazard_calibration_output() -> None:
    by_name = {g.group: g for g in rg.GROUPS}
    assert by_name["Tetralogy of Fallot (ToF)"].untreated_weekly == 0.0080
    assert by_name["Complete AVSD"].untreated_weekly == 0.0234
    assert by_name["Large VSD (death)"].untreated_weekly == 0.0020


def test_deadline_groups_get_no_derived_weekly_rate() -> None:
    by_name = {g.group: g for g in rg.GROUPS}
    assert by_name["Transposition (TGA, simple)"].weekly_risk_after_long_wait is None
    assert by_name["Hypoplastic left heart (HLHS)"].weekly_risk_after_long_wait is None
    tof = by_name["Tetralogy of Fallot (ToF)"].weekly_risk_after_long_wait
    assert tof is not None and 0.0080 < tof < 0.0080 * 1.49


def test_markdown_has_one_line_per_group() -> None:
    lines = rg.table_markdown().strip().splitlines()
    assert len(lines) == 2 + len(rg.GROUPS)
