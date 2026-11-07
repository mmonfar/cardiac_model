# Spec 4: Decision log

**Problem.** Governance needs a record of what was asked, shown and decided.

**What exists.** `decision_log` (local SQLite) and `views/whatif_log.py` (past consultations).

**Acceptance criteria.**
- Append-only: no UPDATE or DELETE in code; a correction is a new row.
- Export to CSV and a one-page print view per row.
- Synthetic data only in demos.

**Tests.** `tests/engine/test_decision_log.py`; `tests/app/test_whatif_screens.py`.
