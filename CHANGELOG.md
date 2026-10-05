# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-10-05

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
- "AI" wording for the search over simulated runs.
- v1 source files from the working tree (still available at `v1-final`).
