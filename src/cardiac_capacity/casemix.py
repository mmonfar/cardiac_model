# ruff: noqa: E501  (long source citations in a data table)
"""Lesion case-mix for the CICU planner.

Each lesion group carries what the cited sources support: the urgency category from the lesion-to-category
map (``risk_groups.LESION_MAP``), a CICU length of stay, a hard deadline counted as an event when missed,
whether it arrives as an unscheduled emergency, a spontaneous-resolution exit, and a staged re-entry (HLHS
stage 2). Where the literature gives no figure the value is the model's own category placeholder and the row says
"awaiting source".

**Arrival shares are synthetic.** No population shares are published for for these lesions; the default mix only
keeps the category shares close to the default (0.08 / 0.15 / 0.30 / 0.47). They are a user input, not a
prevalence claim.

Not modelled (stated, not hidden): a separate cath-lab queue and bridge procedures (BAS then switch), weight-
and age-dependent length of stay (the literature gives direction but no figures), and a patient age clock. Deadlines
therefore count weeks since referral, which for a neonate diagnosed antenatally or at birth is close to age.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StageReentry:
    """A planned later stage that re-enters the list (HLHS: stage 1, then stage 2 after 3-6 months)."""

    group_key: str
    after_weeks: tuple[int, int]  # uniform in [lo, hi)
    interstage_mortality: float
    source: str


@dataclass(frozen=True)
class LesionGroup:
    key: str
    label: str
    cicu_cat: int
    share: float  # synthetic default arrival share (0 for planned stages)
    los_days: float
    los_source: str
    deadline_weeks: int | None = None
    deadline_source: str = ""
    emergency: bool = False
    resolution_weekly: float = 0.0
    resolution_source: str = ""
    stage2: StageReentry | None = None
    complication_late_weeks: int | None = None  # repair after this many weeks adds complications
    complication_excess: float = 0.0
    notes: str = field(default="")


HLHS_STAGE2 = StageReentry(
    "hlhs2",
    (13, 27),
    0.08,
    "Glenn at about 3-6 months; interstage mortality 8% (Staehler et al. 2023, doi:10.3389/fcvm.2023.1239477)",
)

GROUPS: tuple[LesionGroup, ...] = (
    LesionGroup(
        "tga",
        "TGA (simple)",
        1,
        0.04,
        7.0,
        "Dorobantu et al. 2023, doi:10.1016/j.jacadv.2023.100407: ICU stay median 7 d (IQR 5-11), England and Wales n=1,772",
        deadline_weeks=3,
        deadline_source="Switch within 3-4 weeks (Saxena et al. 2019, doi:10.4103/apc.apc_32_19)",
        emergency=True,
    ),
    LesionGroup(
        "tgavsd",
        "TGA with VSD",
        1,
        0.02,
        7.0,
        "Proxy: TGA ICU median 7 d; this source gives post-operative hospital stay only (median 13 d, IQR 9-18); awaiting source for ICU days",
        deadline_weeks=1,
        deadline_source="Faateh et al. 2025, doi:10.1016/j.xjon.2024.10.015: repair mostly in week 1, composite complications aOR 1.49 (1.02-2.15) after day 8",
        emergency=True,
        complication_late_weeks=2,
        complication_excess=0.066,  # 24.0% vs 17.4% composite complication, repair after vs within day 8
    ),
    LesionGroup(
        "hlhs",
        "HLHS (stage 1)",
        1,
        0.02,
        19.6,
        "Iskander et al. 2024, doi:10.3390/jcm13144244: Norwood ICU stay mean 19.6 d (3 studies, 183 patients)",
        deadline_weeks=1,
        deadline_source="Gobergs et al. 2016, doi:10.6001/actamedica.v23i2.3325: fatal untreated, usually within the first week",
        emergency=True,
        stage2=HLHS_STAGE2,
    ),
    LesionGroup(
        "avsd",
        "Complete AVSD",
        2,
        0.15,
        10.0,
        "Awaiting source (no ICU figure found; Al-Wassia et al. 2022, doi:10.1186/s43044-022-00292-8 gives direction only); model category placeholder",
    ),
    LesionGroup(
        "vsd",
        "Large VSD",
        3,
        0.30,
        5.0,
        "Awaiting source (the VSD meta-analysis gives a surgical-minus-catheter difference only); model category placeholder",
    ),
    LesionGroup(
        "tof",
        "Tetralogy of Fallot",
        4,
        0.20,
        3.0,
        "Awaiting source for ICU days (Yang et al. 2019, doi:10.1186/s12872-019-0999-1 gives hospital stay 10-29 d by age); model category placeholder",
    ),
    LesionGroup(
        "other",
        "Small VSD and other routine",
        4,
        0.27,
        3.0,
        "Awaiting source; model category placeholder",
        resolution_weekly=1 - 0.4 ** (1 / 312),  # 60% close within 6 years (132 children)
        resolution_source="Li et al. 2019, doi:10.1002/clc.23173: spontaneous closure 60% of 132 children followed to 6 years; applied to the whole group, so an upper bound",
    ),
    LesionGroup(
        "hlhs2",
        "HLHS (stage 2, planned)",
        3,
        0.0,
        5.0,
        "Iskander et al. 2024, doi:10.3390/jcm13144244: stage II ICU stay mean 5 d (single centre, n=22)",
        notes="Enters the list 13-26 weeks after stage 1; never arrives as a new referral.",
    ),
)


@dataclass(frozen=True)
class CaseMix:
    """Lesion groups and their arrival shares (synthetic unless the user sets them)."""

    groups: tuple[LesionGroup, ...] = GROUPS
    shares: tuple[float, ...] | None = None  # None = each group's default share

    def arrival_shares(self) -> tuple[float, ...]:
        raw = self.shares if self.shares is not None else tuple(g.share for g in self.groups)
        total = sum(raw)
        if total <= 0:
            raise ValueError("case mix shares must not all be zero")
        return tuple(x / total for x in raw)

    def category_shares(self) -> tuple[float, float, float, float]:
        out = [0.0] * 4
        for g, s in zip(self.groups, self.arrival_shares(), strict=True):
            out[g.cicu_cat - 1] += s
        return (out[0], out[1], out[2], out[3])

    def index(self, key: str) -> int:
        for i, g in enumerate(self.groups):
            if g.key == key:
                return i
        raise KeyError(key)


DEFAULT_CASEMIX = CaseMix()


def casemix_table_markdown(mix: CaseMix = DEFAULT_CASEMIX) -> str:
    """The case-mix parameters with their sources, as Markdown for the docs."""
    head = (
        "| Group | CICU cat | Default share (synthetic) | CICU stay, days | Stay source | Deadline | Other |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for g, s in zip(mix.groups, mix.arrival_shares(), strict=True):
        other = []
        if g.emergency:
            other.append("unscheduled arrival")
        if g.resolution_weekly:
            other.append(
                f"leaves the list {g.resolution_weekly * 100:.2f}%/wk ({g.resolution_source})"
            )
        if g.stage2:
            other.append(
                f"stage 2 after {g.stage2.after_weeks[0]}-{g.stage2.after_weeks[1] - 1} wk, interstage mortality {g.stage2.interstage_mortality:.0%}"
            )
        if g.complication_late_weeks:
            other.append(
                f"repair after day 8 adds about {g.complication_excess * 100:.1f} points of composite complications"
            )
        deadline = (
            "none sourced"
            if g.deadline_weeks is None
            else f"{g.deadline_weeks} wk ({g.deadline_source})"
        )
        rows.append(
            f"| {g.label} | {g.cicu_cat} | {s:.0%} | {g.los_days:g} | {g.los_source} | {deadline} | {'; '.join(other) or '-'} |"
        )
    return head + "\n".join(rows) + "\n"
