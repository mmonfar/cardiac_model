# What-if consulting mode: SPEC (week of 2 Nov 2026; build starts Mon 9 Nov)

Status: spec only.

Engine today (read, v2.2.3): `src/cardiac_capacity/cicu_policy.py` (`PolicyParams`, `run_metrics`, `replicate`, seeded streams, `start_mode="today"` with `occupied_now`) and `recommend_cicu.py` (`evaluate_plan`, `recommend`, `plain_words`, seed bands SEED_SELECT / SEED_VALIDATE / SEED_CHECK). Parameters are fixed for the whole run. A shock that starts in week X needs a time-varying hook. This is the one engine change.

## 1. User
A hospital manager. Alone, no training, no thinking navigation. One question per screen, big buttons, plain words, no jargon. Same rules as the planner: a range of futures, not a forecast.

## 2. Example questions (all synthetic in demos)
1. "Three CICU beds are blocked from week 2 for an unknown time." (palliative patients, family stays)
2. "The anaesthetist resigns. Theatre slots drop from 5 to 3 for 6 weeks from week 1."
3. "Infection outbreak: 4 beds closed for 2 to 4 weeks."
4. "A referral surge: 3 extra urgent cases per week for 4 weeks."
5. "Theatre closed for 2 weeks from week 3."

## 3. Inputs that can change (scenario events on a timeline)
| Event | Fields | Maps to |
|---|---|---|
| Block beds | N beds, start week, duration (fixed or range min-max) | `beds` minus N in the window |
| Cut theatre | slots K, start week, duration | `slots` = K in the window (0 = closed) |
| Extra arrivals | M per week, start week, duration, urgency | `weekly_referrals` plus M, urgency mix shifted |
| Unknown duration | min and max weeks | each seeded run draws a duration from the range |

Out-of-range input is refused with a plain message. Start state = today's real list and `occupied_now` (start_mode "today").

## 4. How a scenario re-runs the model
1. Add `events: tuple[Event, ...] = ()` to `PolicyParams`. Default is empty, so every existing result stays identical (golden tests prove it).
2. `_simulate` reads the effective beds, slots and arrivals for each week from the events. No other change.
3. Run baseline (no events) and scenario on the same seeds. Show the difference: list at the end, deteriorations, peak occupancy, urgent days unserved, each with a range (CI).
4. Recovery options: reuse `recommend()` on the scenario (extra lists, surge bed, deferral rules). Say "no feasible plan" when that is true. No free-text answer without a run behind it.
5. Later, own card: a local assistant turns a typed question into events; the user confirms the events before the run.

## 5. Decision log
Local SQLite file, append-only (corrections are new rows, never edits; no UPDATE or DELETE in code). Table `consultation`: id, UTC time, asker, question text, events (JSON), model version, parameter set name, seeds, results shown (JSON, with baseline), decision (choice, by whom, why), optional review date, `corrects_id`. Export to CSV and a one-page print view for governance meetings. Same pattern as the clinical-node run log. Synthetic data only in demos. "What actually happened" can be added later as a new row.

## 6. Screens (plain words)
1. "What happened?" Pick a card: beds blocked, theatre cut, outbreak, more referrals, other.
2. "Tell me more" Few fields, one unit each, ranges allowed ("not sure: 2 to 6 weeks").
3. "Check" One sentence: "3 beds blocked from week 2 for 2 to 6 weeks. Run it?" Yes / change.
4. "What it means" Baseline next to your case: waiting list, deteriorations, beds. Range bars. One line verdict. Disclaimer shown.
5. "What can we do?" Ranked options from `recommend()`, or "no safe plan found".
6. "Record your decision" Choice, name, reason, review date. Saved.
7. "Past consultations" List, open, export.

## 7. Out of scope
Real patient data; forecasts; clinical advice; free-text AI answers; the local assistant (own card later); editing past log rows; push or hosting; cloud or login.

## 8. Licence and disclaimer lines
- Code AGPL-3.0, commercial licence on request. Content CC BY-NC. Independence and data notice as in the README.
- "Research and demonstration software. Not a medical device and not intended for clinical decision-making, diagnosis or treatment. Uses synthetic data only. Results are ranges of possible futures, not a forecast."
- Shown on screen 4, in the export and in the README section.

## 9. Brain (searched 6 Nov)
No published source specific to what-if or scenario methods or bed blocking was found. One loose related source: early discharge and length of stay in acute cardiology (2022). Gaps: scenario and stress testing for hospital capacity; delayed discharge (bed blocking); decision-log and audit practice; run-chart rules (Anhøj). No citations invented.

## 10. Blocker
Run-chart rules work (C6b) is done. Further open-access literature is still to be collected. Station 1 does not depend on new defaults (events default to empty), so the build can start; later default changes flow through.

## 11. Build stations (each at most 1% of a weekly budget, max 40 calls)
| # | Output | Check command (run in cardiac_model) | Cost |
|---|---|---|---|
| 1 | `Event` type and `events` on `PolicyParams`; weekly effective beds, slots, arrivals in `_simulate`; no-event results identical | `python -m pytest tests/engine -q` (adds `test_events.py`) | 1.0% |
| 2 | `whatif.py`: baseline and scenario on shared seeds; ranges and difference; duration ranges | `python -m pytest tests/engine/test_whatif.py -q` | 0.8% |
| 3 | `decision_log.py`: append-only SQLite, CSV export, no UPDATE or DELETE | `python -m pytest tests/engine/test_decision_log.py -q` | 0.7% |
| 4 | Recovery options for a scenario (reuse `recommend`), "no feasible plan" case | `python -m pytest tests/engine/test_whatif_recommend.py -q` | 0.8% |
| 5 | Screens 1-7 in Streamlit, plain words, wordmark once, disclaimer shown | `python -m pytest tests/app -q` | 1.0% |
| 6 | Stress-test library (5 presets), README, CHANGELOG, licence lines, stills at 390 and 1280 px | `python -m pytest -q` | 0.8% |

Total: about 5.1% of a weekly budget, plus about 0.5% for ED review and checks, so about 5.6%. At 10-14% a day, that is one to two working days.

## Brain sources (ED brain_search, 6 Nov)
- `chd-surgery-discharge-barriers-los-2026`: 24.3% of 752 CHD surgery patients had at least 1 discharge barrier; bed availability is one category. Use for the "beds blocked" event range (station 1).
- `or-ms-methods-orthopaedic-care-review` (Hulshof et al. 2012 taxonomy): label each what-if as strategic, tactical or operational in the decision log (station 3).
- `kidney-waiting-list-expansion-scenarios`: example of reporting scenario results as median (IQR) wait; copy this reporting style (station 2).
- `publisher-check-morris-2019-simulation-studies` (ADEMP): state aims, data, estimands, methods and performance for the stress runs (station 6).
- Gap: no published source on decision-log practice for managers was found. It does not block station 1.
