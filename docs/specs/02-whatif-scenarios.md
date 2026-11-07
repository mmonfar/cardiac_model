# Spec 2: What-if scenarios

**Problem.** Something changes (beds blocked, theatre cut, outbreak, more referrals). The manager needs the effect against the normal case, with a range.

**What exists.** `cicu_policy.Event` on `PolicyParams.events`; `whatif.run_whatif` runs normal and scenario on the same seeds (defaults 26 weeks, 30 runs, seed 500); `views/whatif.py` shows six screens, one question each.

**Acceptance criteria.**
- No events gives results identical to before (golden values).
- An empty scenario, weeks outside 1 to 520, or fewer than 2 runs is refused with a plain message.
- Each measure shows baseline, scenario and difference with a range and a verdict.

**Tests.** `tests/engine/test_events.py`, `test_whatif.py`, `test_v21_characterisation.py`; `tests/app/test_whatif_screens.py`.
