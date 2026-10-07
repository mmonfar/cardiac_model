# ruff: noqa: E501  (long source citations in data tables)
"""Explicit, documented parameter sets for the weekly deterioration step.

Two sets, nothing silent:

- ``PLACEHOLDERS``: the values v2 shipped with: the v1 category rates 0.12 / 0.07 / 0.04 / 0.02 per
  week and the long-wait odds multiplier 1.49. None of them is sourced as a rate for these categories.
- ``LITERATURE``: the weekly rates are the sourced untreated hazards of the lesion that the lesion-to-category
  map (``LESION_MAP``) places in each category, and the generic long-wait multiplier is 1.0 because no published
  source supports a generic factor . Anything the literature cannot source stays on the placeholder and is
  marked "awaiting source" in ``notes``.

Both are proposals awaiting a clinician's check. From v2.1 the package and app default is ``LITERATURE``;
``PLACEHOLDERS`` stays only so v2.0 results can be reproduced. ``custom`` builds a "Your figures" set.

Reading the sourced rates. The literature gives weekly hazards of dying (or losing operability) with NO treatment at
all (docs/hazard-calibration-output.md). The model's event is "moves up one urgency category", which
is broader than death. The untreated hazards are used as the only sourced weekly event rates, and they stand as
proxies: an upper bound for death of a managed patient, not an estimate of escalation. A clinician sets the
escalation rate of a medically managed patient; that value is not published in the cited sources.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cardiac_capacity import risk_groups as rg

# Order of the four rates: category 2 to 1, 3 to 2, 4 to 3, 5 to 4 (ward); CICU uses the first three.
RATE_KEYS = ("det_2to1", "det_3to2", "det_4to3", "det_5to4")
PLACEHOLDER_RATES = (0.12, 0.07, 0.04, 0.02)


def _combine(*hazards: float) -> float:
    """Weekly probability of at least one of several independent events."""
    p = 1.0
    for h in hazards:
        p *= 1.0 - h
    return 1.0 - p


@dataclass(frozen=True)
class ParameterSet:
    name: str
    label: str
    rates: tuple[float, float, float, float]
    cicu: tuple[float, float, float, float]  # CICU deterioration_rates: (0, 2 to 1, 3 to 2, 4 to 3)
    long_wait_or: float
    long_wait_weeks: int
    status: str
    notes: str

    def ward_params(self) -> dict[str, Any]:
        """Keys for ``ward_referral_v2`` (``det_*``, ``long_wait_or``, ``long_wait_weeks``)."""
        return {
            **dict(zip(RATE_KEYS, self.rates, strict=True)),
            "long_wait_or": self.long_wait_or,
            "long_wait_weeks": self.long_wait_weeks,
        }

    def cicu_rates(self) -> tuple[float, float, float, float]:
        """``deterioration_rates`` for the CICU modes: (0, 2 to 1, 3 to 2, 4 to 3)."""
        return self.cicu


_BY = {g.group: g for g in rg.GROUPS}


def _hazard(name: str) -> float:
    h = _BY[name].untreated_weekly
    if h is None:
        raise ValueError(f"{name} has no sourced weekly hazard")
    return h


PLACEHOLDERS = ParameterSet(
    name="placeholders",
    label="Placeholders (not sourced; kept for comparison with v2.0)",
    rates=PLACEHOLDER_RATES,
    cicu=(0.0, 0.05, 0.02, 0.01),  # the CICU mode's own v1 defaults (CicuParams)
    long_wait_or=rg.LONG_WAIT_OR,
    long_wait_weeks=26,
    status="placeholder, not sourced",
    notes=(
        "Category rates are the v1 values; the long-wait odds multiplier 1.49 is the TGA+VSD post-operative "
        "composite-complication OR (not a waiting-list factor)."
    ),
)

LITERATURE = ParameterSet(
    name="literature",
    label="Published literature (default)",
    rates=(
        _hazard("Complete AVSD"),  # category 2 (emergency): complete AVSD, 2.34 %/wk (weeks 0-26)
        _combine(
            _hazard("Large VSD (death)"), _hazard("Large VSD (loss of operability)")
        ),  # category 3: large VSD, death or loss of operability, 1.23 %/wk
        _hazard("Tetralogy of Fallot (ToF)"),  # category 4: ToF elective window, 0.80 %/wk
        0.0,  # category 5 to 4: no published rate, so none is assumed (listed as a data gap)
    ),
    cicu=(
        0.0,
        _hazard("Complete AVSD"),
        _combine(_hazard("Large VSD (death)"), _hazard("Large VSD (loss of operability)")),
        _hazard("Tetralogy of Fallot (ToF)"),
    ),
    long_wait_or=1.0,
    long_wait_weeks=26,
    status="awaiting clinical check",
    notes=(
        "Category 1 has no rate: its lesions (TGA, TGA+VSD, HLHS, obstructed TAPVC) are deadlines plus a bridge. "
        "Category 5 to 4 has no published rate, so none is assumed (0%). Long-wait multiplier 1.0: no published source supports a generic factor."
    ),
)

SETS: Mapping[str, ParameterSet] = {PLACEHOLDERS.name: PLACEHOLDERS, LITERATURE.name: LITERATURE}
DEFAULT_SET = LITERATURE.name  # v2.1: the default is the published-literature set


def custom(
    cat2_to_1: float, cat3_to_2: float, cat4_to_3: float, cat5_to_4: float, long_wait_or: float
) -> ParameterSet:
    """The user's own figures (weekly probabilities, 0-1). Clearly labelled, never the default."""
    return ParameterSet(
        name="custom",
        label="Your figures",
        rates=(cat2_to_1, cat3_to_2, cat4_to_3, cat5_to_4),
        cicu=(0.0, cat2_to_1, cat3_to_2, cat4_to_3),
        long_wait_or=long_wait_or,
        long_wait_weeks=26,
        status="entered by the user",
        notes="Figures entered by the user; not checked against any source.",
    )


def get(name: str) -> ParameterSet:
    try:
        return SETS[name]
    except KeyError:
        raise ValueError(f"unknown parameter set {name!r}; choose from {sorted(SETS)}") from None


def rates_table_markdown() -> str:
    """The two sets side by side, as Markdown for the docs."""
    rows = [
        "| Transition | Placeholders (ward / CICU) | Literature-based | Basis for the literature value |",
        "|---|---|---|---|",
    ]
    basis = (
        "Complete AVSD untreated hazard, weeks 0-26 (guideline: 54% alive at 6 mo)",
        "Large VSD: death 0.20% and loss of operability 1.03% per week, combined as independent events",
        "ToF untreated hazard, weeks 0-52 (66% survive 1 y)",
        "Awaiting source: v1 placeholder kept",
    )
    names = ("2 to 1", "3 to 2", "4 to 3", "5 to 4")
    for i, n in enumerate(names):
        rows.append(
            f"| Category {n} | {PLACEHOLDERS.rates[i] * 100:.2f}% / {'' if i == 3 else format(PLACEHOLDERS.cicu[i + 1] * 100, '.2f') + '%'} | {LITERATURE.rates[i] * 100:.2f}% | {basis[i]} |"
        )
    rows.append(
        f"| Long-wait odds multiplier (after {LITERATURE.long_wait_weeks} weeks) | {PLACEHOLDERS.long_wait_or} | {LITERATURE.long_wait_or} | No source supports a generic factor  |"
    )
    return "\n".join(rows) + "\n"
