# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [2.2.3] - 2026-10-14

### Fixed
- **One logo, top left.** The wordmark showed twice on desktop (side panel and headline bar) and not at all on a phone. It is now a single image in Streamlit's logo slot, top left, on every screen size; the headline bar no longer carries it. A test fails if the wordmark is added anywhere else.
- **Phone: the inputs can be opened again.** The style that hid Streamlit's toolbar also hid the button that opens the side panel on a phone. Only the toolbar menu is hidden now.

## [2.2.2] - 2026-10-12

### Fixed
- **The recommendation now aims to clear the waiting list.** The summary rule was "stops the list growing without extra cancellations" (the same rule as v2.1; v2.1 only recommended theatre sessions plus beds because its list grew to 110). That left 38 children waiting at week 52 with "Add 2 CICU beds". The rule is now: the smallest change that clears the list (at most one week of new referrals waiting at week 52, in 9 of 10 simulated years), adds no more than 2 cancellations a year, and keeps average CICU occupancy at or below your comfortable level (default 85%). For the default example service it recommends "Add 2 theatre sessions and 2 CICU beds": list 0 (0 to 5), cancellations 26 (30 if nothing changes), occupancy 49%.
- The option table column "Chance the list is shorter" is now "Chance the list is cleared". If no option clears the list, the headline says so.
- New tests pin the default example and the rule. Summary scroll budget re-checked: 390 px 2.8, 768 px 1.6, 1280 px 1.8 screens.

## [2.2.1] - 2026-10-12

### Changed
- **No invented figure in the defaults.** The transposition-with-VSD deterioration used a 1-week exposure interval that the source (Faateh 2025) does not state, and its odds ratio measures complications after surgery, not deterioration while waiting. The cell is now a gap ("enter your figure"); the odds ratio is quoted as text only. The default run adds no deterioration. 72 cells are now 18 filled / 23 proxy / 31 gap. The weekly-hazard conversion stays in the code for sources that state a waiting time.
- **Scroll budget met on the Decision summary:** 390 px 2.9 screens (was 4.6), 768 px 1.7, 1280 px 2.0. Explanations sit behind "What this means" and "Which ... " disclosures; staffing text and the phone table are shorter.
- **Sticky headline bar** on every page: the recommendation and the do-nothing result stay in view while scrolling (checked by script at 390, 768 and 1280 px).
- The "Children who got worse after the window" tile only appears when you enter a weekly chance. Wording no longer says "left panel" ("Your service today" instead).
- README and docs give the test command with `PYTHONPATH=src` (another installed copy of the package can shadow the repository).

## [2.2.0] - 2026-10-12

### Changed
- **The planner works by diagnosis.** Twelve diagnoses replace the urgency scale on every screen. Urgency is derived inside the engine from each diagnosis's published operating window and is never shown or entered.
- **Diagnosis table with a source on every value** (`cardiac_capacity.diagnoses`): 12 diagnoses x 6 parameters = 72 cells, 18 published for exactly this, 24 from a nearby published figure, 30 with no published figure. CICU and ward stays and the case mix now come from two new published papers (acuity paper, J Am Heart Assoc 2026, doi:10.1161/jaha.125.048547; UK national audit, doi:10.1136/openhrt-2014-000157).
- **Gaps are visible.** A diagnosis with no CICU stay shows "enter your figures" and is left out of the default recommendation; the summary says which and why. Today 7 of 12 diagnoses are planned.
- **Deterioration while waiting** (superseded in 2.2.1: no default figure) is derived from a published odds ratio for late versus timely repair: risk ratio by Zhang and Yu, then a constant weekly hazard, with the 95% interval as the uncertainty band. One diagnosis (transposition with VSD) has such a ratio; the rest show "enter your figures".
- New pages: **By diagnosis** (status per cell, "your figures" per diagnosis, one reset button) and **Assumptions and sources**. The v2.1 ward and CICU detail pages leave the app (they used the urgency scale); their engines and tests stay (`CARDIAC_LEGACY_V21=1` shows them).
- Summary page: charts and the per-diagnosis table are collapsed by default to cut scrolling.

### Added
- `tests/golden/v21.json` and `tests/engine/test_v21_characterisation.py`: v2.1 behaviour pinned before the change (migrate-with-parity).
- `docs/v2.1-vs-v2.2.md`, before/after stills at 390, 768 and 1280 px in `docs/screenshots/v2.2/`.

### Known limits
- Not clinically checked. Summary scroll budget not yet met on a phone (4.6 screens, budget 3) or desktop (2.8, budget about 2). Sticky headline bar not built.

## [2.1.0] - 2026-10-07

### Changed
- **First screen is a one-screen decision summary**: what we need to do, what happens if we do nothing (waiting list, cancelled operations, children who get more urgent, over 52 weeks), the effect of each lever (theatre sessions, CICU beds, both), staffing as a limit you enter, and a panel of what the model assumes because data is missing.
- **Defaults are the published literature.** The planner now starts on the literature figures, each with a DOI in the README table and in the app. "Your figures" can be entered instead and is labelled as such. The earlier placeholder set stays in the code only so version 2.0 results can be reproduced.
- Stable-to-routine weekly rate is 0% (no published rate; none assumed) instead of a 2% placeholder.
- Plain titles, labelled axes with units, and a "What this means" line under every chart on all pages. Pages renamed: Decision summary, Detail: ward beds, Detail: CICU plan.
- Phone-width layout checked at 390 px.
- README rewritten around the question the tool answers; screenshots added in `docs/screenshots/`.

- The recommendation avoids options that raise cancelled operations (tolerance 2 a year) and states the trade-off when none can; the table and chart show days with every CICU bed full next to average occupancy; the Streamlit toolbar and Deploy button are hidden.

### Added
- `cardiac_capacity.evidence`: one list of every default, its source and the gap it stands in for (feeds the README table and the in-app panel).
- `cardiac_capacity_planner.scenarios`: the comparison and staffing check behind the first screen, with tests.

## [2.0.0] - 2026-10-05

### Why (summary of fixes found when checking v1 against its own arithmetic)

| v1 behaviour | Problem | v2 |
|---|---|---|
| CICU occupancy was counted from the waiting list (backlog x stay / 7) | It over-read occupancy about 5-fold at the default settings and moved the wrong way: more surgery shortened the list and so lowered the reported load. No capacity ever passed | Occupancy is counted from patients who actually had surgery (cases a week x stay), bed by bed and day by day |
| The CICU test was inherited: "urgent cases are cleared and load fits" | It looks only at urgent cases and ignores the routine list. Priority scheduling always clears urgent cases first, so it said nothing about the backlog | Replaced by the objective above (stable list, occupancy at or below target, life-threatening first, optional surge bed). The old test is still shown for comparison |
| Beds were released once a week | Short stays were held for a full week, which inflated ward occupancy and cancellations | Beds are freed on the discharge day (theatre Monday to Friday) |
| One simulated run chose the recommendation | The recommended set-up cleared all 26-week waits in only 77-86% of fresh runs | The recommendation is chosen on one block of seeds and re-tested on fresh seeds; the success rate and its interval are shown |
| A fixed sentence told the user the recommendation was reliable whatever the numbers | It was text, not a result | Removed. The page shows the measured success rate instead |
| Deterioration drawn as one Poisson total, victims picked at random, a hard jump to category 1 at 26 weeks | Patients did not deteriorate according to their own category | One draw per patient per week on the patient's own category. Two start modes: from today's list, or from a settled state |

Measured in [`docs/v1-vs-v2.md`](docs/v1-vs-v2.md) (100 seeds per scenario, fresh seeds for the out-of-sample figures).


v1 is preserved at the tag `v1-final` and is superseded by this release.

### Added
- CICU mode with a recommended plan: elective cases per week and an optional surge bed, under a clear objective (waiting list no longer growing, mean occupancy at or below a target that defaults to 85% and is user-adjustable, life-threatening cases first and never waiting for a bed, surge bed only when needed, otherwise shown as optional with its cost per deterioration avoided).
- Stochastic CICU engine with a per-patient weekly deterioration draw, a bed limit, an occupancy ceiling for elective cases and an optional surge bed counted in bed-days.
- Ward engine v2: beds freed on the actual discharge day, deterioration per patient on the patient's own category, two start modes (from today's list, or from a settled state), separate seeded random streams.
- Recommender that reports the success rate on fresh seeds with a Wilson confidence interval; success threshold user-adjustable (default 90%).
- Two parameter sets, `PLACEHOLDERS` (default) and `LITERATURE` (selectable, labelled as awaiting a clinical check), with a lesion-to-urgency-category map and an optional lesion case mix.
- Optional v1 comparison panel on both pages (off by default).
- Documentation of results and sources: v1 vs v2 delta tables, parameter tables with DOIs, a sanity check against published ranges, hazard calibration; scripts in `analysis/` regenerate them.
- Bundled theme and fonts (Plus Jakarta Sans and Space Grotesk, SIL Open Font License 1.1); no external font service and no dependency outside PyPI.
- Installable package (`pip install -e .`), root `app.py` entry point, test suite (engine and app).

### Changed
- CICU occupancy is now counted from patients who had surgery, not from the waiting list (v1 over-read it about 5-fold at the defaults and moved the wrong way with more surgery).
- The inherited "urgent cases cleared and load fits" test is replaced by the new objective and kept only as a labelled comparison.
- README rewritten: plain-language scope, honest limitations, parameters marked sourced or awaiting source.
- Licence files updated to the AGPL-3.0-or-later licence pack, with the third-party font table.
- The CICU cost line is shown in model cost units (no currency).

### Removed
- The fixed text that called the recommendation reliable whatever the numbers; the page now shows the measured success rate.
- v1 source files from the working tree (still available at `v1-final`).
