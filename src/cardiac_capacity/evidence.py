# ruff: noqa: E501  (long source citations in a data table)
"""Every default the planner starts with, and where it comes from.

One list feeds the README table and the in-app "Where the numbers come from" panel, so they cannot
disagree. ``basis`` is ``literature`` (a published figure), ``proxy`` (a published figure used for a
neighbouring quantity, with the gap stated) or ``assumption`` (no published figure: shown to the user
as a data gap and meant to be replaced by their own).
"""

from __future__ import annotations

from dataclasses import dataclass

SAXENA = "Saxena et al. 2019, doi:10.4103/apc.apc_32_19"
MARTINS = "Martins et al. 2018, doi:10.21470/1678-9741-2018-0019"
DOROBANTU = "Dorobantu et al. 2023, doi:10.1016/j.jacadv.2023.100407"
ISKANDER = "Iskander et al. 2024, doi:10.3390/jcm13144244"
STAEHLER = "Staehler et al. 2023, doi:10.3389/fcvm.2023.1239477"
FAATEH = "Faateh et al. 2025, doi:10.1016/j.xjon.2024.10.015"


@dataclass(frozen=True)
class Default:
    name: str
    value: str
    basis: str  # literature | proxy | assumption
    source: str
    gap: str  # what the model assumes because data is missing ("" if none)


DEFAULTS: tuple[Default, ...] = (
    Default(
        "Patients moving from urgent to life-threatening, per week",
        "2.34%",
        "proxy",
        f"{SAXENA} (complete AVSD, untreated, weeks 0-26)",
        'Published rates are for children with no treatment at all. They are an upper bound, used as a stand-in for "becomes more urgent" while waiting.',
    ),
    Default(
        "Patients moving from semi-urgent to urgent, per week",
        "1.23%",
        "proxy",
        f"{SAXENA} (large VSD: death 0.20% + loss of operability 1.03%)",
        'Same limit: an untreated rate used as a stand-in for "becomes more urgent".',
    ),
    Default(
        "Patients moving from routine to semi-urgent, per week",
        "0.80%",
        "proxy",
        f"{SAXENA}; {MARTINS} (tetralogy of Fallot, untreated, weeks 0-52)",
        'Same limit: an untreated rate used as a stand-in for "becomes more urgent".',
    ),
    Default(
        "Stable patients becoming routine-urgent (ward model only), per week",
        "0%",
        "assumption",
        "none published",
        "No published rate was found, so none is assumed. Real stable patients do sometimes worsen.",
    ),
    Default(
        "Extra risk after a long wait (26+ weeks)",
        "none (x1.0)",
        "assumption",
        f"{FAATEH} reports 1.49, but for complications after one repair, not for waiting",
        "No published source gives a general long-wait factor, so none is applied. Waiting probably does add risk.",
    ),
    Default(
        "Which lesion counts as which urgency category",
        "proposal",
        "proxy",
        f"{DOROBANTU}; Gobergs et al. 2016, doi:10.6001/actamedica.v23i2.3325; {ISKANDER}; Ji et al. 2021, doi:10.3389/fcvm.2021.775578",
        "A proposal built from published operating windows. It needs a cardiologist's check.",
    ),
    Default(
        "CICU stay: transposition 7 days, HLHS first operation 19.6 days (case mix only)",
        "as stated",
        "literature",
        f"{DOROBANTU}; {ISKANDER}",
        "",
    ),
    Default(
        "Infants lost between first and second HLHS operation (case mix only)",
        "8%",
        "literature",
        f"{STAEHLER}",
        "",
    ),
    Default(
        "CICU stay by urgency group (14 / 10 / 5 / 3 days)",
        "14 / 10 / 5 / 3",
        "assumption",
        "none published for these groups",
        "Typical stays differ by hospital and case mix. Replace with your own average stays.",
    ),
    Default(
        "Share of referrals in each urgency group",
        "8% / 15% / 30% / 47%",
        "assumption",
        "none published (population shares are not available)",
        "Illustrative. Your referral mix will differ.",
    ),
    Default(
        "Waiting list, referrals a week, theatre sessions, CICU beds",
        "60, 5, 5, 10",
        "assumption",
        "an illustrative unit, not a literature figure",
        "These describe a service, not a disease. Enter your own.",
    ),
    Default(
        "Safe CICU occupancy target",
        "85%",
        "assumption",
        "no published level was found",
        "Many units quote a figure around this level, but it is your call.",
    ),
    Default(
        "Staff who can cover theatre sessions and CICU beds",
        "not set",
        "assumption",
        "no published figure; it depends on your rosters",
        "Staffing is not limiting until you enter a cap. Enter yours to see which options are out of reach.",
    ),
)


def gaps() -> list[Default]:
    """The defaults that rest on a stand-in or on no published figure."""
    return [d for d in DEFAULTS if d.basis != "literature"]


def table_markdown() -> str:
    rows = [
        "| Parameter | Default | Basis | Source | What the model assumes because data is missing |",
        "|---|---|---|---|---|",
    ]
    for d in DEFAULTS:
        rows.append(f"| {d.name} | {d.value} | {d.basis} | {d.source} | {d.gap or '-'} |")
    return "\n".join(rows) + "\n"
