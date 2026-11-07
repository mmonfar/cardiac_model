# Spec 3: Safe recovery plan (screen 5)

**Problem.** After a shock, the manager asks what can be done. The word "safe" must mean one fixed thing.

**What exists.** `whatif_recommend.recover` and `SAFE_MEANING`; full definition in `docs/sdd.md` section 3.

**Acceptance criteria.**
- Safe = no worse than the normal case on every check, same seeds; the normal case is always safe.
- At most 3 options, ranked by mean children who get worse; search up to 3 extra cases a week, with and without the surge bed.
- If none is safe: "No safe plan found", the checks where the closest plan is worse, no safe plan offered.
- The children-who-got-worse figure shows the Saxena et al. 2019 untreated-risk label.

**Tests.** `tests/engine/test_whatif_recommend.py`, `tests/app/test_whatif_screens.py`.
