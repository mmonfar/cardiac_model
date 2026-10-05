# ruff: noqa: E501  (long source citations in a data table)
"""Condition-group weekly risk of waiting. Awaiting clinical check.

Every number comes from the sourced work in ``docs/``: the untreated weekly hazards of
``docs/hazard-calibration-output.md`` (generated from published survival anchors) and the
odds/risk ratios in the cited literature. Nothing here was
downloaded or invented. Two limits are stated in the table itself:

- The untreated hazards are **upper bounds** (no prostaglandin, septostomy, diuretics or cath bridge).
  The risk of a *medically managed* patient waiting on a list is not sourced; a clinician sets it.
- Only one published odds ratio concerns the cost of **delay** (TGA+VSD repair after day 8, aOR 1.49,
  composite complications). It is applied as the generic long-wait odds multiplier. The other published
  ratios concern the timing of repair or the type of operation and are listed but not used.

``weekly_risk_after_long_wait`` multiplies the odds of the baseline weekly hazard by the long-wait OR. For
TGA and HLHS the relevant object is a deadline plus a bridge, not a weekly rate, so no rate is derived.
"""

from __future__ import annotations

from dataclasses import dataclass

STATUS = "awaiting clinical check"
LONG_WAIT_OR = 1.49
LONG_WAIT_SOURCE = "Faateh et al. 2025, doi:10.1016/j.xjon.2024.10.015 (US PHIS, n=1,005): repair after day 8, composite complications aOR 1.49"


def odds_multiplied(p: float, odds_ratio: float) -> float:
    """Probability after multiplying the odds of ``p`` by ``odds_ratio``."""
    return p * odds_ratio / (1 - p + p * odds_ratio)


@dataclass(frozen=True)
class GroupRisk:
    group: str
    untreated_weekly: float | None  # first-year (or first-interval) weekly hazard, an upper bound
    interval: str
    rate_source: str
    published_ratio: str
    use: str
    apply_long_wait: bool
    status: str = STATUS

    @property
    def weekly_risk_after_long_wait(self) -> float | None:
        if self.untreated_weekly is None or not self.apply_long_wait:
            return None
        return odds_multiplied(self.untreated_weekly, LONG_WAIT_OR)


GROUPS: tuple[GroupRisk, ...] = (
    GroupRisk(
        "Tetralogy of Fallot (ToF)",
        0.0080,
        "weeks 0-52 (0.29% weeks 52-156)",
        "Untreated survival 66% at 1 y (guideline and case reports); exact piecewise hazard",
        "Neonatal vs later repair, mortality OR 1.68 (1.47-1.92): cost of operating too EARLY, not of waiting",
        "Weekly upper bound for a patient with no treatment; U-shaped timing, so not 'earlier is better'",
        True,
    ),
    GroupRisk(
        "Transposition (TGA, simple)",
        0.0433,
        "weeks 0-52 (about 90% dead at 1 y untreated)",
        "Indian guideline 2019 (chd-indications-timing-intervention): mean untreated life 0.65 y",
        "None for waiting. Switch within 3-4 weeks is a deadline",
        "Deadline plus bridge (septostomy), not a rate: no long-wait multiplier applied",
        False,
    ),
    GroupRisk(
        "TGA with VSD",
        None,
        "week 1 repair is the norm",
        "No sourced weekly hazard (expert table: about 1 y untreated)",
        "Repair after day 8: composite complications aOR 1.49; mortality 3.1% whatever the timing",
        "Source of the generic long-wait odds multiplier (1.49)",
        False,
    ),
    GroupRisk(
        "Complete AVSD",
        0.0234,
        "weeks 0-26 (1.65% weeks 26-52)",
        "Guideline: 54% alive at 6 mo, 35% at 12 mo; Weibull shape 0.77",
        "None for waiting (weight below 4 kg lengthens ventilation and stay)",
        "Weekly upper bound; irreversible pulmonary vascular disease can start by 6 months (Down syndrome)",
        True,
    ),
    GroupRisk(
        "Large VSD (death)",
        0.0020,
        "weeks 0-52",
        "Guideline: about 10% die in year 1 (heart failure)",
        "None for waiting",
        "Weekly upper bound for death",
        True,
    ),
    GroupRisk(
        "Large VSD (loss of operability)",
        0.0103,
        "weeks 0-52",
        "Guideline: 52% develop irreversible pulmonary vascular disease (historic series)",
        "None for waiting",
        "Deadline-like transition (operability), shown as a weekly rate for stress tests only",
        True,
    ),
    GroupRisk(
        "Hypoplastic left heart (HLHS)",
        None,
        "weeks 0-4 (50% in week 1 untreated)",
        "About 95% die early untreated (hybrid vs Norwood meta-analysis, Gobergs et al. 2016, doi:10.6001/actamedica.v23i2.3325)",
        "Hybrid vs Norwood interstage mortality RR 1.61 (1.10-2.33); home monitoring interstage 2.5% vs 10.3%: "
        "about the operation and the interstage, not the wait",
        "Deadline plus bridge (prostaglandin): no weekly rate is derived",
        False,
    ),
)


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.2f}%"


def table_markdown() -> str:
    """The table a clinician checks, as Markdown."""
    head = (
        "| Group | Untreated weekly hazard (upper bound) | Interval | Weekly risk after long-wait "
        "rule (odds x 1.49) | Rate source | Published OR/RR (and why used or not) | Use in model | "
        "Status |\n|---|---|---|---|---|---|---|---|\n"
    )
    rows = [
        f"| {g.group} | {_pct(g.untreated_weekly)} | {g.interval} | "
        f"{_pct(g.weekly_risk_after_long_wait)} | {g.rate_source} | {g.published_ratio} | {g.use} | "
        f"{g.status} |"
        for g in GROUPS
    ]
    return head + "\n".join(rows) + "\n"


@dataclass(frozen=True)
class LesionCategory:
    """Where a lesion group sits in the model's urgency categories .

    ``ward_cat`` is the 1-5 ward category (1 = life-threatening); ``cicu_cat`` the 1-4 CICU category
    (routine merges ward 4 and 5). The basis is the sourced window or deadline, not a clinician's
    judgement; it is a proposal awaiting a clinical check.
    """

    group: str
    ward_cat: int
    cicu_cat: int
    basis: str
    source: str
    status: str = STATUS


LESION_MAP: tuple[LesionCategory, ...] = (
    LesionCategory(
        "Transposition (TGA, simple)",
        1,
        1,
        "Hard deadline: arterial switch within 3-4 weeks before the left ventricle regresses; about 90% dead at 1 y untreated",
        "Saxena et al. 2019, doi:10.4103/apc.apc_32_19; Dorobantu et al. 2023, doi:10.1016/j.jacadv.2023.100407 (median age 9.5 d)",
    ),
    LesionCategory(
        "TGA with VSD",
        1,
        1,
        "Repair mostly in week 1 (median 6 days); complications rise when repair is after day 8",
        "Faateh et al. 2025, doi:10.1016/j.xjon.2024.10.015",
    ),
    LesionCategory(
        "Hypoplastic left heart (HLHS)",
        1,
        1,
        "Fatal untreated, usually within the first week; stage 1 needs prostaglandin then a neonatal operation",
        "Gobergs et al. 2016, doi:10.6001/actamedica.v23i2.3325; Iskander et al. 2024, doi:10.3390/jcm13144244",
    ),
    LesionCategory(
        "Obstructed TAPVC (not one of the five groups)",
        1,
        1,
        "Obstruction means no safe wait: emergency surgery in 18% of the series",
        "Ji et al. 2021, doi:10.3389/fcvm.2021.775578",
    ),
    LesionCategory(
        "Complete AVSD",
        2,
        2,
        "Highest sourced weekly hazard among lesions that are not deadlines (2.34% weeks 0-26; 54% alive at 6 months); irreversible pulmonary vascular disease can start by 6 months in Down syndrome; median age at repair 191 days in one series",
        "Saxena et al. 2019, doi:10.4103/apc.apc_32_19; Al-Wassia et al. 2022, doi:10.1186/s43044-022-00292-8",
    ),
    LesionCategory(
        "Large VSD",
        3,
        3,
        "Sourced risks are heart-failure death (about 10% in year 1, 0.20%/wk) and irreversible pulmonary vascular disease (52%, onset in infancy in four-fifths, 1.03%/wk); no repair window is given in the cited sources (awaiting source), so it sits below AVSD on hazard",
        "Saxena et al. 2019, doi:10.4103/apc.apc_32_19",
    ),
    LesionCategory(
        "Tetralogy of Fallot (ToF)",
        4,
        4,
        "Elective window 3-6 months when asymptomatic or mildly symptomatic (immediately if severe, which moves the child up); too-early repair costs mortality",
        "Martins et al. 2018, doi:10.21470/1678-9741-2018-0019; Rampengan et al. 2025, doi:10.4103/apc.apc_228_24",
    ),
    LesionCategory(
        "Small or moderate VSD and other routine lesions",
        5,
        4,
        "No sourced weekly risk; spontaneous closure in 60% of 132 children with isolated VSD followed to 6 years, so waiting is often benign",
        "Li et al. 2019, doi:10.1002/clc.23173; Saxena et al. 2019, doi:10.4103/apc.apc_32_19",
    ),
)


def lesion_map_markdown() -> str:
    """The lesion-to-category proposal as Markdown."""
    head = (
        "| Lesion group | Ward category | CICU category | Basis (window or deadline) | Brain source | Status |\n"
        "|---|---|---|---|---|---|\n"
    )
    rows = [
        f"| {m.group} | {m.ward_cat} | {m.cicu_cat} | {m.basis} | {m.source} | {m.status} |"
        for m in LESION_MAP
    ]
    return head + "\n".join(rows) + "\n"
