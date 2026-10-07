# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-10-07

### Changed
- **First screen is a one-screen decision summary**: what we need to do, what happens if we do nothing (waiting list, cancelled operations, children who get more urgent, over 52 weeks), the effect of each lever (theatre sessions, CICU beds, both), staffing as a limit you enter, and a panel of what the model assumes because data is missing.
- **Defaults are the published literature.** The planner now starts on the literature figures, each with a DOI in the README table and in the app. "Your figures" can be entered instead and is labelled as such. The earlier placeholder set stays in the code only so version 2.0 results can be reproduced.
- Stable-to-routine weekly rate is 0% (no published rate; none assumed) instead of a 2% placeholder.
- Plain titles, labelled axes with units, and a "What this means" line under every chart on all pages. Pages renamed: Decision summary, Detail: ward beds, Detail: CICU plan.
- Phone-width layout checked at 390 px.
- README rewritten around the question the tool answers; screenshots added in `docs/screenshots/`.

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
