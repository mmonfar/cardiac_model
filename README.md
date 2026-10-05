# Cardiac Capacity Planner (v2.0)

Cardiac surgery capacity planner: simulates a waiting list, theatre slots and beds, and shows a range of outcomes with a transparent recommendation.
**Status: Prototype · synthetic data only · not a medical device.**

---

## What it does

A paediatric cardiac surgery service has two linked bottlenecks: theatre time and the beds behind it (ward beds and cardiac intensive care, CICU). Adding theatre slots to clear a backlog can simply move the queue to the beds. This tool simulates both, week by week, many times over, with random referrals, random length of stay and random deterioration while patients wait. It then shows the range of results rather than a single forecast.

The planner has two pages (two modes of one model):

- **Ward referral** (`/ward`): a waiting list feeding a surgical ward. It reports how many patients are still waiting 26 weeks or more at a goal week, ward occupancy and cancelled operations, and recommends the smallest set-up (beds, then theatre slots) that clears all 26-week waits in at least a chosen share of simulated futures (default 90%, adjustable).
- **CICU** (`/cicu`): a waiting list feeding a cardiac intensive care unit. It recommends a plan, meaning elective cases per week and whether to open an extra (surge) bed, under this objective:
  - the waiting list is cleared or at least no longer growing (no endless queue);
  - mean CICU occupancy stays at or below a target (default 85%, you can change it);
  - life-threatening (category 1) cases are always operated first and never wait for a bed;
  - a surge bed is recommended only when it is needed to get a workable plan. Otherwise it is shown as optional, with its cost (bed-days opened per deterioration avoided) so you can decide.

Every recommendation is shown with the share of fresh simulated futures in which it holds, and a confidence interval for that share. Inputs are yours to change; the defaults are synthetic.

## How to run

Python 3.11 or newer.

```bash
git clone https://github.com/mmonfar/cardiac_model.git
cd cardiac_model
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip install -e ".[dev]"
.venv/bin/streamlit run src/cardiac_capacity_planner/app.py
.venv/bin/pytest                          # optional: the test suite
```

Everything installs from PyPI (numpy, pandas, plotly, streamlit). The theme and its two fonts are bundled, so the app needs no other folder or external service.

## What changed from v1 and why

v1 (tag `v1-final`: `git checkout v1-final`) is the single-file ward model. v2 keeps the idea and fixes problems found when checking it against its own arithmetic:

| v1 behaviour | Problem | v2 |
|---|---|---|
| CICU occupancy was counted from the waiting list (backlog x stay / 7) | It over-read occupancy about 5-fold at the default settings and moved the wrong way: more surgery shortened the list and so lowered the reported load. No capacity ever passed | Occupancy is counted from patients who actually had surgery (cases a week x stay), bed by bed and day by day |
| The CICU test was inherited: "urgent cases are cleared and load fits" | It looks only at urgent cases and ignores the routine list. Priority scheduling always clears urgent cases first, so it said nothing about the backlog | Replaced by the objective above (stable list, occupancy at or below target, life-threatening first, optional surge bed). The old test is still shown for comparison |
| Beds were released once a week | Short stays were held for a full week, which inflated ward occupancy and cancellations | Beds are freed on the discharge day (theatre Monday to Friday) |
| One simulated run chose the recommendation | The recommended set-up cleared all 26-week waits in only 77-86% of fresh runs | The recommendation is chosen on one block of seeds and re-tested on fresh seeds; the success rate and its interval are shown |
| A fixed sentence told the user the recommendation was reliable whatever the numbers | It was text, not a result | Removed. The page shows the measured success rate instead |
| "AI" wording for a search | It is a plain search over simulated runs | Wording removed throughout |
| Deterioration drawn as one Poisson total, victims picked at random, a hard jump to category 1 at 26 weeks | Patients did not deteriorate according to their own category | One draw per patient per week on the patient's own category. Two start modes: from today's list, or from a settled state |

The changes are measured in [`docs/v1-vs-v2.md`](docs/v1-vs-v2.md) (100 seeds per scenario, fresh seeds for the out-of-sample figures).

## The method in brief

- Weekly loop: age the list, deteriorate patients (one random draw each), add referrals (Poisson), operate by category then by longest wait, and hold a bed for each stay (a Gamma-distributed length of stay, rounded up to whole days).
- Theatre runs five days a week; weekly slots are spread over those days.
- Seeded Monte Carlo: each run has its own seed, so every result can be reproduced. Reported ranges are 5th, 50th and 95th percentiles.
- Recommendation: search the options, test each on a block of seeds, keep those that pass in at least the threshold share of futures, pick the best, then re-test on fresh seeds. Success rates carry Wilson confidence intervals.
- CICU objective: an epsilon-constraint formulation (the constraints above) rather than a weighted sum, because the weights between different harms are a clinical judgement that the model does not make for you.

## Parameters: sourced and awaiting source

Two parameter sets are offered on both pages. **Placeholders** is the default: the v1 category rates (0.12 / 0.07 / 0.04 / 0.02 per week) and a long-wait odds multiplier of 1.49. None of these is sourced as a rate for these categories. **Literature-based** can be selected and is labelled as awaiting a clinical check. Defaults will change only after the sourced values have been reviewed by a clinician.

The literature-based weekly rates are untreated hazards (death or loss of operability with no treatment at all). They are upper bounds, used here as proxies for "moves up one urgency category". The real weekly risk for a medically managed child on a list is not published in the sources used, so it is marked *awaiting source*.

| Parameter | Placeholders (default) | Literature-based | Status | Source |
|---|---|---|---|---|
| Category 2 to 1, weekly | 12.00% (CICU 5.00%) | 2.34% (complete AVSD, weeks 0-26) | Sourced as untreated hazard, proxy only | Saxena et al. 2019, doi:10.4103/apc.apc_32_19 |
| Category 3 to 2, weekly | 7.00% (CICU 2.00%) | 1.23% (large VSD: death 0.20% + loss of operability 1.03%) | Sourced as untreated hazard, proxy only | Saxena et al. 2019, doi:10.4103/apc.apc_32_19 |
| Category 4 to 3, weekly | 4.00% (CICU 1.00%) | 0.80% (tetralogy of Fallot, weeks 0-52) | Sourced as untreated hazard, proxy only | Saxena et al. 2019, doi:10.4103/apc.apc_32_19; Martins et al. 2018, doi:10.21470/1678-9741-2018-0019 |
| Category 5 to 4, weekly | 2.00% | 2.00% (placeholder kept) | Awaiting source | none |
| Long-wait odds multiplier (after 26 weeks) | 1.49 | 1.0 | 1.49 is a post-operative complication odds ratio for one lesion (TGA+VSD repaired after day 8), not a waiting-list factor, so it is not supported as a generic value | Faateh et al. 2025, doi:10.1016/j.xjon.2024.10.015 |
| Lesion to urgency category map | n/a | proposal (TGA, TGA+VSD, HLHS category 1; complete AVSD 2; large VSD 3; ToF 4; small VSD and routine 4-5) | Proposal from sourced windows and deadlines, awaiting clinical check | Dorobantu et al. 2023, doi:10.1016/j.jacadv.2023.100407; Gobergs et al. 2016, doi:10.6001/actamedica.v23i2.3325; Iskander et al. 2024, doi:10.3390/jcm13144244; Ji et al. 2021, doi:10.3389/fcvm.2021.775578; Al-Wassia et al. 2022, doi:10.1186/s43044-022-00292-8; Rampengan et al. 2025, doi:10.4103/apc.apc_228_24; Li et al. 2019, doi:10.1002/clc.23173 |
| CICU stay: TGA 7 days, HLHS stage 1 19.6 days, HLHS stage 2 5 days | case mix only | as stated | Sourced | Dorobantu et al. 2023, doi:10.1016/j.jacadv.2023.100407; Iskander et al. 2024, doi:10.3390/jcm13144244 |
| CICU stay: other lesions; ward stays; arrival shares; occupancy target (85%) | category defaults | category defaults | Awaiting source (arrival shares are synthetic user inputs) | none |
| HLHS interstage mortality 8% | case mix only | 8% (2.5% with home monitoring, 10.3% without) | Sourced | Staehler et al. 2023, doi:10.3389/fcvm.2023.1239477 |

Full tables, the derivation of the weekly hazards and the case-mix parameters: [`docs/risk-table.md`](docs/risk-table.md), [`docs/hazard-calibration-output.md`](docs/hazard-calibration-output.md) (script: `analysis/hazard_calibration.py`). A comparison of the engines against published ranges is in [`docs/sanity-check.md`](docs/sanity-check.md): stays are plausible; occupancy and waiting times could not be judged for lack of a comparable published figure.

## Limitations

- Prototype on synthetic parameters. It has not been validated against real data and gives no forecast.
- No deaths are modelled while waiting, only moves up an urgency category.
- The managed-patient escalation rate, CICU occupancy and waiting-time ranges for a comparable unit, and a safe occupancy target are awaiting a published source.
- Not modelled: a catheter-lab queue and bridge procedures, weight- and age-dependent stays, an age clock for each patient.
- When demand exceeds what the occupancy ceiling can serve, the honest answer is more beds, fewer referrals or a lower target; the planner says "no plan found" rather than inventing one.
- The recommended weekly cases sit on a plateau: read the number as "at least this many", and the floor (the least that stops the list growing) as the minimum.
- Cost per surge bed is shown, but no cost threshold is built in.

## Project layout

```
src/cardiac_capacity/          engines: ward (v1, v2), CICU (v1, v2, stochastic plan), recommenders, parameter sets, case mix
src/cardiac_capacity_planner/  Streamlit app (pages: Ward referral, CICU) and the bundled theme and fonts
tests/                         engine and app tests (synthetic data only)
analysis/                      scripts that regenerate the figures in docs/
docs/                          v1 vs v2 results, parameter tables, sanity check
```

## Licence

Code is licensed under **AGPL-3.0-or-later** (see [`LICENSE`](LICENSE)); a commercial licence is available on request from the author via [LinkedIn](https://www.linkedin.com/in/martin-monteagudo-farina/). Non-code content is under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Details in [`LICENSING.md`](LICENSING.md). The two bundled fonts keep their own SIL Open Font License 1.1 (`src/cardiac_capacity_planner/brand/fonts/OFL.txt`).

## Disclaimer

Research and demonstration software. Not a medical device and not intended for clinical decision-making, diagnosis or treatment. Provided "as is", without warranty of any kind; the author accepts no liability for any use. Uses synthetic data only.

Built with AI assistance (Claude); all code and claims reviewed by the author. See [`LICENSE`](LICENSE) for the full warranty terms.

## Independence and data notice

**Independence and data notice.** This is a personal project, developed independently in my own time and on my own equipment. It is not affiliated with, endorsed by, or representative of my employer or any other organisation. It contains no employer data, systems, code or confidential information. All data in this repository is synthetic or fictitious, and any resemblance to real patients, staff or events is coincidental. Views are my own.
