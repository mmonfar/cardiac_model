# ruff: noqa: E501, N802  (long source citations in a data table)
"""The diagnosis x parameter table of the v2.2 planner.

Every cell is a value with its source and DOI, or a visible gap. ``status`` is ``F`` (filled: a published figure
for exactly this quantity and diagnosis), ``P`` (proxy: a published figure for a neighbouring quantity, the
mismatch stated) or ``G`` (gap: nothing published in the sources reviewed). Nothing here is invented. The only free
inputs are service size; a user can override any cell per diagnosis ("your figures").

Urgency is never an input. It is derived inside the engine from each diagnosis's operating window
(``urgency_class``). A diagnosis without a CICU stay or a case-mix share is **left out of the default
recommendation** and the screen says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardiac_capacity.casemix import CaseMix, DelayEffect, LesionGroup, StageReentry

COLUMNS = (
    ("window", "Operating window (weeks)"),
    ("deterioration", "Weekly deterioration once past the window"),
    ("waiting", "Waiting-list outcome"),
    ("cicu", "CICU stay (days)"),
    ("ward", "Ward stay (days)"),
    ("share", "Share of operations"),
)
UK_TOTAL = 36_641  # surgical episodes, UK national audit 2000-2010

SAXENA = "Saxena et al. 2019, doi:10.4103/apc.apc_32_19"
MARTINS = "Martins et al. 2018, doi:10.21470/1678-9741-2018-0019"
DOROBANTU = "Dorobantu et al. 2023, doi:10.1016/j.jacadv.2023.100407"
FAATEH = "Faateh et al. 2025, doi:10.1016/j.xjon.2024.10.015"
ISKANDER = "Iskander et al. 2024, doi:10.3390/jcm13144244"
STAEHLER = "Staehler et al. 2023, doi:10.3389/fcvm.2023.1239477"
JI = "Ji et al. 2021, doi:10.3389/fcvm.2021.775578"
LI = "Li et al. 2019, doi:10.1002/clc.23173"
GOBERGS = "Gobergs et al. 2016, doi:10.6001/actamedica.v23i2.3325"
CARDARELLI = "Cardarelli et al. 2018, doi:10.1001/jamanetworkopen.2018.4707"
ACUITY = "J Am Heart Assoc 2026, doi:10.1161/jaha.125.048547 (one US centre, 2018-2023, Table 2)"
UK = "UK national audit 2000-2010, Open Heart 2015, doi:10.1136/openhrt-2014-000157 (Table 2, 36,641 operations)"
D1_GAP = (
    "No published odds or risk ratio for late versus timely repair in the sources reviewed. Enter your figure."
)


@dataclass(frozen=True)
class Cell:
    status: str  # F | P | G
    value: float | None
    text: str
    source: str = ""

    @property
    def usable(self) -> bool:
        return self.value is not None


def F(value: float | None, text: str, source: str) -> Cell:
    return Cell("F", value, text, source)


def P(value: float | None, text: str, source: str) -> Cell:
    return Cell("P", value, text, source)


def G(text: str = "Not in the published sources we hold. Enter your figure.") -> Cell:
    return Cell("G", None, text, "")


def _share(n: int) -> Cell:
    return P(
        n / UK_TOTAL,
        f"{n:,} of {UK_TOTAL:,} operations ({100 * n / UK_TOTAL:.1f}%). Share of operations, not of referrals.",
        UK,
    )


@dataclass(frozen=True)
class Diagnosis:
    key: str
    label: str
    window: Cell
    deterioration: Cell
    waiting: Cell
    cicu: Cell
    ward: Cell
    share: Cell
    delay: DelayEffect | None = None  # the OR/RR behind the deterioration cell

    def cell(self, name: str) -> Cell:
        return getattr(self, name)

    def cells(self) -> tuple[Cell, ...]:
        return tuple(self.cell(n) for n, _ in COLUMNS)


_OTHER_N = UK_TOTAL - (2359 + 1393 + 428 + 3583 + 1357 + 931 + 2243 + 3012 + 2053 + 644 + 832)

DIAGNOSES: tuple[Diagnosis, ...] = (
    Diagnosis(
        "tof",
        "Tetralogy of Fallot",
        F(
            26,
            "Elective repair at 3 to 6 months if symptoms are none or mild; at once if severe. The window ends at 26 weeks.",
            MARTINS,
        ),
        G(D1_GAP),
        P(
            None,
            "Untreated survival 66% at 1 year, 49% at 3 years. Upper bound for a child with no treatment.",
            SAXENA,
        ),
        F(4, "Median 4 days (IQR 2 to 10), repair, one US centre", ACUITY),
        F(4, "Median 4 days (IQR 3 to 7), acute care unit", ACUITY),
        _share(2359),
    ),
    Diagnosis(
        "tga",
        "Transposition (TGA), intact septum",
        F(
            4,
            "Arterial switch within 3 to 4 weeks of life, before the left ventricle regresses",
            SAXENA,
        ),
        G(D1_GAP),
        P(
            None,
            "About 90% die in year 1 untreated. Upper bound for a child with no treatment.",
            SAXENA,
        ),
        F(7, "Median 7 days (IQR 5 to 11), England and Wales, n=1,772", DOROBANTU),
        P(
            9,
            "Median 9 days (IQR 6 to 12), acute care unit; switch with or without VSD closure",
            ACUITY,
        ),
        _share(1393),
    ),
    Diagnosis(
        "tgavsd",
        "Transposition with VSD",
        F(1, "Repair mostly in week 1 (median age 6 days); complications rise after day 8", FAATEH),
        G(
            "Published: odds ratio 1.49 (95% CI 1.02 to 2.15) for complications after surgery when repair is after day 8 "
            "(Faateh et al. 2025, doi:10.1016/j.xjon.2024.10.015). The source states no waiting time, so it gives no weekly chance. "
            "Not used. Enter your figure."
        ),
        P(None, "Expert estimate: about 1 year untreated (selection-biased).", CARDARELLI),
        F(8, "Median 8 days (IQR 5 to 14) in ICU after the operation, US PHIS, n=1,005", FAATEH),
        P(
            9,
            "Median 9 days (IQR 6 to 12), acute care unit; switch with or without VSD closure",
            ACUITY,
        ),
        _share(428),
    ),
    Diagnosis(
        "vsd",
        "Ventricular septal defect (VSD)",
        G("The guideline list of closure times did not survive conversion. Enter your window."),
        G(D1_GAP),
        F(
            None,
            "60% of 132 children with isolated VSD closed on their own by 6 years. Used as a weekly exit from the list.",
            LI,
        ),
        F(3, "Median 3 days (IQR 1 to 10), repair, one US centre", ACUITY),
        F(4, "Median 4 days (IQR 3 to 7), acute care unit", ACUITY),
        _share(3583),
    ),
    Diagnosis(
        "avsd",
        "Complete AVSD",
        P(
            26,
            "No stated window. Irreversible lung vessel disease can start by 6 months in Down syndrome.",
            SAXENA,
        ),
        G(D1_GAP),
        P(None, "54% alive at 6 months, 35% at 12 months untreated. Upper bound.", SAXENA),
        G("No CICU figure for this diagnosis."),
        G(
            "Only total hospital stay is published (Al-Wassia 2022, doi:10.1186/s43044-022-00292-8). It includes the CICU."
        ),
        _share(1357),
    ),
    Diagnosis(
        "hlhs",
        "Hypoplastic left heart (HLHS), first operation",
        F(
            1,
            "Fatal untreated, usually within the first week; first operation in the newborn period",
            GOBERGS,
        ),
        G(D1_GAP),
        F(
            None,
            "Loss between first and second operation 8% (2.5% with home monitoring, 10.3% without)",
            STAEHLER,
        ),
        F(19.6, "Mean 19.6 days (SD 20.6), 3 studies, 183 children", ISKANDER),
        F(14, "Median 14 days (IQR 6 to 24), acute care unit, first operation", ACUITY),
        _share(931),
    ),
    Diagnosis(
        "coarct",
        "Coarctation of the aorta",
        G("No stated window. Critical coarctation is a newborn problem (median age 11 days)."),
        G(D1_GAP),
        G(),
        G("The only CICU figure is for a catheter bridge, not for surgery."),
        G(),
        _share(2243),
    ),
    Diagnosis(
        "pda",
        "Patent ductus arteriosus (PDA)",
        G("No upper window. Many close on their own."),
        G(D1_GAP),
        P(
            None,
            "Preterm closure on its own: 34% by day 4 below 28 weeks (improvement, not deterioration).",
            "de Klerk et al. 2020, doi:10.3389/fped.2020.00541",
        ),
        G(),
        G(),
        _share(3012),
    ),
    Diagnosis(
        "asd",
        "Atrial septal defect (ASD)",
        G("The guideline list of closure ages did not survive conversion. Enter your window."),
        G(D1_GAP),
        G(),
        F(1, "Median 1 day (IQR 1 to 1), repair, one US centre", ACUITY),
        F(2, "Median 2 days (IQR 2 to 3), acute care unit", ACUITY),
        _share(2053),
    ),
    Diagnosis(
        "tapvc",
        "Obstructed TAPVC",
        F(0, "Obstruction means no safe wait: 18% needed emergency surgery", JI),
        G(D1_GAP),
        P(None, "Obstruction in 26% of children; early deaths 8.7% (after surgery).", JI),
        F(3, "Median 3 days (IQR 2 to 4), one centre, newborns", JI),
        G(),
        _share(644),
    ),
    Diagnosis(
        "truncus",
        "Truncus, interrupted arch, pulmonary atresia with VSD",
        G(),
        G(D1_GAP),
        P(
            None,
            "Expert estimate untreated: truncus 1 year, interrupted arch 1 year (selection-biased).",
            CARDARELLI,
        ),
        G(),
        G(),
        _share(276 + 260 + 296),
    ),
    Diagnosis(
        "other",
        "Other / not listed",
        G("Enter a window, or the group has no deadline and is scheduled last."),
        G(D1_GAP),
        P(
            None,
            "Norway: of 2,359 infants with severe heart disease, 10% died, 58% of those before surgery.",
            "Wik et al. 2020, doi:10.1136/archdischild-2019-317581",
        ),
        G(),
        G(),
        P(
            _OTHER_N / UK_TOTAL,
            f"All other operations in the same audit ({_OTHER_N:,} of {UK_TOTAL:,}). Share of operations, not of referrals.",
            UK,
        ),
    ),
)
BY_KEY = {d.key: d for d in DIAGNOSES}

HLHS_STAGE2 = StageReentry(
    "hlhs2",
    (13, 27),
    0.08,
    f"Second operation at about 3 to 6 months; loss between operations 8% ({STAEHLER})",
)
VSD_CLOSURE_WEEKLY = 1 - 0.4 ** (1 / 312)  # 60% closed within 6 years (Li 2019)


def urgency_class(window_weeks: float | None) -> int:
    """Internal scheduling class from the operating window. Never shown to a user.

    Less slack means earlier treatment. No window means scheduled last.
    """
    if window_weeks is None:
        return 4
    if window_weeks <= 4:
        return 1
    if window_weeks <= 13:
        return 2
    if window_weeks <= 30:
        return 3
    return 4


def counts() -> dict[str, int]:
    out = {"F": 0, "P": 0, "G": 0}
    for d in DIAGNOSES:
        for c in d.cells():
            out[c.status] += 1
    return out


@dataclass(frozen=True)
class Mix:
    casemix: CaseMix
    included: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]  # (label, why)
    yours: tuple[str, ...]  # "label: cell" entered by the user


def _effective(d: Diagnosis, name: str, over: dict[str, float]) -> float | None:
    if name in over:
        return over[name]
    return d.cell(name).value


def build_mix(overrides: dict[str, dict[str, float]] | None = None) -> Mix:
    """Case mix of the diagnoses that have the figures to be planned, plus what was left out and why.

    ``overrides`` maps a diagnosis key to {"window", "deterioration", "cicu", "ward", "share"}; blank
    entries are simply absent. Shares are renormalised over the included diagnoses.
    """
    overrides = overrides or {}
    groups: list[LesionGroup] = []
    included: list[str] = []
    excluded: list[tuple[str, str]] = []
    yours: list[str] = []
    labels = dict(COLUMNS)
    for d in DIAGNOSES:
        over = overrides.get(d.key, {})
        yours.extend(f"{d.label}: {labels[k].lower()}" for k in over)
        los = _effective(d, "cicu", over)
        share = _effective(d, "share", over)
        if los is None or not share:
            excluded.append((d.label, "no CICU stay" if los is None else "no share of operations"))
            continue
        window = _effective(d, "window", over)
        det = over.get("deterioration")
        delay = DelayEffect.yours(det) if det is not None else d.delay
        late = d.key == "tgavsd"
        groups.append(
            LesionGroup(
                d.key,
                d.label,
                urgency_class(window),
                float(share),
                float(los),
                "yours" if "cicu" in over else d.cicu.source,
                deadline_weeks=None if window is None else int(window) + 1,
                deadline_source="yours" if "window" in over else d.window.source,
                emergency=window is not None and window <= 1,
                resolution_weekly=VSD_CLOSURE_WEEKLY if d.key == "vsd" else 0.0,
                resolution_source=LI if d.key == "vsd" else "",
                stage2=HLHS_STAGE2 if d.key == "hlhs" else None,
                complication_late_weeks=2 if late else None,
                complication_excess=0.066 if late else 0.0,
                delay=delay,
            )
        )
        included.append(d.key)
    if "hlhs" in included:
        groups.append(
            LesionGroup(
                "hlhs2",
                "HLHS, second operation (planned)",
                urgency_class(26),
                0.0,
                5.0,
                f"{ISKANDER}: mean 5 days (one centre, n=22)",
                notes="Enters the list 13 to 26 weeks after the first operation.",
            )
        )
    return Mix(CaseMix(tuple(groups)), tuple(included), tuple(excluded), tuple(yours))


def table_markdown() -> str:
    """The whole table with sources, for the README and the Assumptions tab."""
    head = (
        "| Diagnosis | "
        + " | ".join(label for _, label in COLUMNS)
        + " |\n|---|"
        + "---|" * len(COLUMNS)
        + "\n"
    )
    rows = []
    for d in DIAGNOSES:
        cells = " | ".join(
            f"**{c.status}** {c.text}" + (f" ({c.source})" if c.source else "") for c in d.cells()
        )
        rows.append(f"| {d.label} | {cells} |")
    return head + "\n".join(rows) + "\n"


def unpublished_inputs(mix: Mix) -> int:
    """Cells the run uses that are proxies (``P``) rather than exact published figures."""
    n = 0
    for key in mix.included:
        d = BY_KEY[key]
        n += sum(1 for c in (d.window, d.cicu, d.share) if c.status == "P" and c.usable)
        if d.delay is not None:
            n += 1
    return n
