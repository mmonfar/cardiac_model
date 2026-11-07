# Software design document: Cardiac Capacity Planner

Status: prototype. Not a medical device. Synthetic data only. Changes are in `CHANGELOG.md`.

## 1. Purpose
Help a hospital manager see what happens to a cardiac waiting list and the CICU (cardiac intensive care unit) if theatre time, beds or staff change. Results are a range of possible years, not a forecast. Defaults come only from published sources (each shows source and DOI); users may enter their own figures.

## 2. Scope
In: the planner by diagnosis (decision summary, by diagnosis, assumptions and sources), and the what-if mode (six short screens plus a past-consultations page with an append-only decision log).
Out: real patient data, forecasts, clinical advice, free-text AI answers, cloud hosting, login (see `docs/WHAT_IF_SPEC.md` section 7).

## 3. Structure and contract
Two packages in `src/`:

- `cardiac_capacity` (engine, no UI). Interfaces:
  - `cicu_policy`: `PolicyParams`, `Event`, `RunMetrics`, `run_metrics`, `run_frame`, `replicate(params, weeks, n, seed0)`. Every run is seeded and reproducible. `events` default to empty, so results without events do not change.
  - `recommend_cicu`: `evaluate_plan`, `recommend`, `check_plan`, `failure_reasons`, `plain_words`.
  - `recommend`, `protocol`, `ward_referral_v2`, `montecarlo` (`run`, `summarize`, `weekly_band`): ward referral model and repeat-run statistics.
  - `whatif`: `run_whatif(params, events, weeks=26, runs=30, seed0=500)` runs the normal case and the scenario on the same seeds; `check_events`, `verdict_line`.
  - `whatif_recommend`: `recover(params, events, weeks, runs, seed0)` returns a `Recovery` of `Option`s; `worse_than_normal`; `SAFE_MEANING`.
  - `decision_log`: `open_log`, `append`, `rows`, `get`, `export_csv`, `print_view`. Local SQLite, append-only; corrections are new rows.
  - `parameter_sets` (`get`, `custom`), `diagnoses`, `evidence`, `casemix`, `risk_groups`: the published figures and their status.
- `cardiac_capacity_planner` (Streamlit app): `app.py` (entry; pages), `views/` (`summary`, `diagnosis`, `whatif`, `whatif_log`, `assumptions`), `ui` (CSS, header, `sidebar_brand`), `charts`, `whatif_ui`, `presentation`, `default_cache`, and the bundled `brand/` theme. The views only collect inputs and lay out; all numbers come from the engine.

Run: `streamlit run src/cardiac_capacity_planner/app.py` (also `app.py` at the repository root).

### Screen 5 ("What can we do?"): safe plan
Defined in `whatif_recommend.SAFE_MEANING` and shown once on screen: "Safe here means: no worse than the normal case on every check."

- Normal case: the same parameters without the events, current plan, same seeds as the what-if run.
- A plan is safe when, on every check (waiting list grew, unit above the occupancy target, a life-threatening case waited for a bed), it fails in no more futures than the normal case does (`worse_than_normal` is empty; the only tolerance is float rounding, 1e-9).
- The search tries the current number of cases a week plus up to `MAX_EXTRA_CASES` (3) more, one at a time, with and without the extra (surge) bed. Safe plans are ranked by mean children who get worse, then slots; at most `MAX_OPTIONS` (3) are shown.
- If none is safe the answer says "No safe plan found", names the checks where the closest plan is worse (`best_effort`), and offers no safe plan.
- The "children who got worse" figure carries the label `whatif_ui.DETERIORATION_SOURCE`: weekly risks of 2.34% (complete AVSD), 1.23% (large VSD) and 0.80% (tetralogy of Fallot) from Saxena et al. 2019, doi:10.4103/apc.apc_32_19. They are risks without treatment, so the real figure for a child who is managed while waiting is lower. A clinician must check it.

## 4. Acceptance criteria
1. Every result is reproducible from its seed; baseline and scenario use the same seeds.
2. Every published value shows source and DOI; a missing figure shows "enter your figures" and the diagnosis is left out of the default recommendation. Nothing is invented.
3. With no events, engine results equal the pinned golden values (`tests/golden/v21.json`).
4. What-if refuses an empty scenario, weeks outside 1 to 520, and fewer than 2 runs, with a plain message.
5. Screen 5 uses the safe-plan definition above, and shows "No safe plan found" when none exists.
6. The decision log has no UPDATE or DELETE; it exports to CSV.
7. The wordmark appears once, in the Streamlit logo slot; the page uses brand tokens only.
8. The not-a-medical-device disclaimer and the Independence and data notice are in the README.

## 5. Tests
`PYTHONPATH=src python -m pytest -q` (260 tests at commit a13483b). `PYTHONPATH=src` is required if another install of `cardiac_capacity` exists. `tests/engine` covers the engine, `tests/app` runs the app with Streamlit `AppTest`, `tests/golden` holds pinned values. Specs: `docs/specs/`.

## 6. Safety and data
Research and demonstration software. Not a medical device and not intended for clinical decision-making, diagnosis or treatment. Data is synthetic or published figures; no patient data. Licence: AGPL-3.0 with a commercial licence on request (`LICENSING.md`); content CC BY-NC.
