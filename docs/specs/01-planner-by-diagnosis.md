# Spec 1: Planner by diagnosis

**Problem.** A manager needs to know what to do about the waiting list and CICU beds, without set-up and without reading a model.

**What exists.** The first screen (`views/summary.py`) answers: what do we need to do, what if we do nothing, what does each lever do, what does staffing allow. `views/diagnosis.py` and `views/assumptions.py` show every value with its status and source.

**Acceptance criteria.**
- The first screen shows an answer with no input.
- Each published value shows source and DOI; diagnoses with no figure are marked and left out of the default recommendation.
- Only service size is entered by the user; urgency is derived from the operating window.
- Results show a range from repeated seeded runs.

**Tests.** `tests/app/test_summary_page.py`, `test_diagnosis_pages.py`, `test_planner_app.py`, `test_planner_presentation.py`; engine: `tests/engine/test_recommend.py`, `test_recommend_cicu.py`, `test_diagnoses.py`, `test_parameter_sets.py`.
