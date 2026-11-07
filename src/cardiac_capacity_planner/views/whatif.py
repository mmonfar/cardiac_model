# ruff: noqa: E501  (plain-language page text)
"""What if: six short screens, one question each. Pick what happened, say more, check, see what it means,
see what can be done, record the decision. Past consultations are on their own page.

Every sentence comes from a run (``cardiac_capacity.whatif`` and ``whatif_recommend``). A range of possible
futures, not a forecast. Synthetic data only.
"""

from __future__ import annotations

from datetime import date, timedelta
from html import escape

import streamlit as st

from cardiac_capacity import decision_log, whatif, whatif_recommend
from cardiac_capacity_planner import ui, whatif_ui as wu

STEPS = ("What happened?", "Tell me more", "Check", "What it means", "What can we do?", "Record your decision")
S = st.session_state
S.setdefault("wi_step", 1)


def go(step: int) -> None:
    S["wi_step"] = step


def start_over() -> None:
    for k in ("wi_choice", "wi_name", "wi_why", "wi_use_review", "wi_review", "wi_card", "wi_answers", "wi_result", "wi_recovery", "wi_saved", "wi_error"):
        S.pop(k, None)
    S["wi_step"] = 1


def pick_card(key: str) -> None:
    S["wi_card"] = key
    S.pop("wi_error", None)
    S["wi_step"] = 2


def to_check(a: wu.Answers) -> None:
    try:
        wu.make_event(a)
    except ValueError as err:  # the engine says it in plain words
        S["wi_error"] = str(err)
        return
    S.pop("wi_error", None)
    S["wi_answers"] = a
    S.pop("wi_result", None)
    S.pop("wi_recovery", None)
    S.pop("wi_saved", None)
    S["wi_step"] = 3


def row(label: str, share: float, worse: float, end: float, pick: bool = False) -> str:
    return (
        f'<tr class="{"pick" if pick else ""}"><td class="opt" data-label="Option">{escape(label)}</td>'
        f'<td class="num" data-label="Meets every condition">{share:.0%} of futures</td>'
        f'<td class="num" data-label="Children who get worse">{worse:.0f}</td>'
        f'<td class="num" data-label="List at the end">{end:.0f}</td></tr>'
    )


step = int(S["wi_step"])
ui.band("What if something changes?", f"Step {step} of 6 · {STEPS[step - 1]}")
card_key = S.get("wi_card", "beds")
answers: wu.Answers | None = S.get("wi_answers")

# ---------------------------------------------------------------- 1 What happened?
if step == 1:
    st.markdown("### What happened?")
    st.caption("Pick the one that is closest. Each test compares your case with the normal case.")
    cols = st.columns(len(wu.CARDS))
    for col, (key, (label, help_, _kind, _lvl)) in zip(cols, wu.CARDS.items()):
        with col:
            st.button(label, key=f"card_{key}", on_click=pick_card, args=(key,), type="primary", use_container_width=True)
            st.caption(help_)
    st.page_link("views/whatif_log.py", label="Open past what-if consultations", icon=":material/history:")

# ---------------------------------------------------------------- 2 Tell me more
elif step == 2:
    label, help_, kind, _lvl = wu.CARDS[card_key]
    st.markdown(f"### Tell me more: {label.lower()}")
    if card_key == "other":
        kind = st.selectbox("What changes?", list(wu.KIND_NAMES), format_func=lambda k: wu.KIND_NAMES[k])
    if kind == "block_beds":
        amount = st.number_input(f"How many of the {wu.BEDS} CICU beds are blocked? (beds)", 1, wu.BEDS, 4 if card_key == "outbreak" else 3, 1)
    elif kind == "cut_theatre":
        amount = st.number_input(f"How many operations a week can still happen? (now {wu.SLOTS}; 0 = theatre closed)", 0, wu.SLOTS - 1, 3, 1)
    else:
        amount = st.number_input("How many extra new referrals come each week? (children a week)", 1, 30, 3, 1)
    urgency = None
    if kind == "extra_arrivals":
        urgency = st.selectbox("How urgent are they?", list(wu.URGENCY), format_func=lambda k: wu.URGENCY[k])
    c1, c2 = st.columns(2)
    start = c1.number_input("It starts in week (0 = now)", 0, 104, {"beds": 2, "outbreak": 0}.get(card_key, 1), 1)
    unsure = c2.toggle("Not sure how long", value=card_key in ("beds", "outbreak"))
    default_lo, default_hi = (2, 4) if card_key == "outbreak" else ((2, 6) if card_key == "beds" else (4, 6))
    d1, d2 = st.columns(2)
    lo = d1.number_input("Shortest time (weeks)" if unsure else "How long (weeks)", 1, 104, default_lo, 1)
    hi = d2.number_input("Longest time (weeks)", int(lo), 104, max(default_hi, int(lo)), 1) if unsure else lo
    if S.get("wi_error"):
        st.error(S["wi_error"])
    ans = wu.Answers(kind, float(amount), int(start), int(lo), int(hi), urgency)
    cols = st.columns([1, 1, 3])
    cols[0].button("Back", on_click=go, args=(1,), key="b2", use_container_width=True)
    cols[1].button("Next: check", type="primary", on_click=to_check, args=(ans,), key="n2", use_container_width=True)

# ---------------------------------------------------------------- 3 Check
elif step == 3 and answers:
    st.markdown("### Check")
    st.markdown(
        f'<div class="ccp-do"><div class="mm-label-sm">I will test this</div><div class="headline">{escape(wu.sentence(answers))}</div>'
        f'<div class="because">Run it? The test starts from a service with {wu.SLOTS} operations a week, {wu.BEDS} CICU beds, '
        f"{wu.BACKLOG} children waiting and {wu.REFERRALS:.0f} new referrals a week, and follows it for {whatif.DEFAULT_WEEKS} weeks. "
        "It takes about 10 seconds.</div></div>",
        unsafe_allow_html=True,
    )
    cols = st.columns([1, 1, 3])
    cols[0].button("Change", on_click=go, args=(2,), key="chg", use_container_width=True)
    cols[1].button("Yes, run it", type="primary", on_click=go, args=(4,), key="run", use_container_width=True)

# ---------------------------------------------------------------- 4 What it means
elif step == 4 and answers:
    event = wu.make_event(answers)
    if "wi_result" not in S:
        with st.spinner("Running 30 possible futures, with and without the change…"):
            S["wi_result"] = whatif.run_whatif(wu.base_params(), (event,))
    res: whatif.WhatIfResult = S["wi_result"]
    top = [res.get("list_end"), res.get("det_events"), res.get("cat1_unserved_days")]
    st.markdown(
        f'<div class="ccp-do"><div class="mm-label-sm">{escape(wu.sentence(answers))}</div>'
        f'<div class="headline">{escape(whatif.verdict_line(res))}</div></div>',
        unsafe_allow_html=True,
    )
    ui.kpis(
        [
            (wu.fmt(m.field, m.scenario.p50), m.label, f"Normal case: <b>{wu.fmt(m.field, m.baseline.p50)}</b> · {wu.VERDICT_WORDS[m.verdict]}")
            for m in top
        ]
    )
    rows = "".join(
        f'<tr><td class="opt" data-label="Measure">{escape(m.label)}</td>'
        f'<td class="num" data-label="Normal case">{wu.fmt(m.field, m.baseline.p50)}</td>'
        f'<td class="num" data-label="Your case">{wu.fmt(m.field, m.scenario.p50)}</td>'
        f'<td class="num" data-label="Change">{escape(wu.change_text(m.field, m.difference))}</td>'
        f'<td data-label="Clear?">{wu.VERDICT_WORDS[m.verdict]}</td></tr>'
        for m in res.measures
    )
    st.markdown(
        '<table class="ccp-table"><thead><tr><th>Measure</th><th>Normal case</th><th>Your case</th><th>Change</th><th>Clear?</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )
    cols = st.columns([1, 1, 1, 2])
    cols[0].button("Back", on_click=go, args=(3,), key="b4", use_container_width=True)
    cols[1].button("What can we do?", type="primary", on_click=go, args=(5,), key="n4", use_container_width=True)
    cols[2].button("Record decision", on_click=go, args=(6,), key="r4", use_container_width=True)
    st.markdown(
        f'<div class="ccp-quiet">Median of {res.runs} possible futures over {res.weeks} weeks; range = 5th to 95th percentile. {escape(decision_log.DISCLAIMER)}</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------- 5 What can we do?
elif step == 5 and answers:
    event = wu.make_event(answers)
    if "wi_recovery" not in S:
        with st.spinner("Searching for plans, about 1 minute…"):
            S["wi_recovery"] = whatif_recommend.recover(wu.base_params(), (event,))
    rec: whatif_recommend.Recovery = S["wi_recovery"]
    rows = ""
    if rec.found:
        best = wu.plan_label(rec.options[0].slots, rec.options[0].surge)
        st.markdown(
            f'<div class="ccp-do"><div class="mm-label-sm">Best option</div><div class="headline">{escape(best)}</div>'
            f'<div class="because">{escape(rec.message)}</div></div>',
            unsafe_allow_html=True,
        )
        rows = "".join(row(f"{o.rank}. {wu.plan_label(o.slots, o.surge)}", o.share_ok, o.worsen_mean, o.list_end_mean, o.rank == 1) for o in rec.options)
    else:
        st.markdown(
            f'<div class="ccp-do"><div class="mm-label-sm">Result</div><div class="headline">No safe plan found.</div>'
            f'<div class="because">{escape(rec.message.removeprefix("No safe plan found. "))}</div></div>',
            unsafe_allow_html=True,
        )
        be = rec.best_effort
        if be is not None:
            rows = row(f"Closest: {wu.plan_label(be.slots, be.surge)}", be.share_ok, be.worsen_mean, be.list_end_mean, True)
    dn = rec.do_nothing
    rows += row(f"Keep the current plan ({wu.plan_label(dn.slots, dn.surge)})", dn.share_ok, dn.worsen_mean, dn.list_end_mean)
    st.markdown(
        '<table class="ccp-table"><thead><tr><th>Option</th><th>Meets every condition</th><th>Children who get worse</th><th>List at the end</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )
    cols = st.columns([1, 1, 3])
    cols[0].button("Back", on_click=go, args=(4,), key="b5", use_container_width=True)
    cols[1].button("Record decision", type="primary", on_click=go, args=(6,), key="n5", use_container_width=True)

# ---------------------------------------------------------------- 6 Record your decision
elif step == 6 and answers:
    event = wu.make_event(answers)
    if "wi_result" not in S:
        with st.spinner("Running 30 possible futures…"):
            S["wi_result"] = whatif.run_whatif(wu.base_params(), (event,))
    res = S["wi_result"]
    rec = S.get("wi_recovery")
    st.markdown("### Record your decision")
    if S.get("wi_saved"):
        st.success(f"Saved as consultation number {S['wi_saved']}. It cannot be edited; a correction is a new entry.")
    choices = ["Keep the current plan", "Another plan (explain below)"]
    if rec is not None:
        choices = [f"Plan: {wu.plan_label(o.slots, o.surge)}" for o in rec.options] + choices
    choice = st.radio("What did you decide?", choices, key="wi_choice")
    name = st.text_input("Your name", key="wi_name")
    why = st.text_area("Why?", height=80, key="wi_why")
    use_review = st.toggle("Set a review date", value=False, key="wi_use_review")
    review = st.date_input("Review on", value=date.today() + timedelta(days=28), min_value=date.today(), key="wi_review") if use_review else None

    def save() -> None:
        # A button callback runs before the script re-runs: read the live widget values, not the ones above.
        choice, name, why = S["wi_choice"], S["wi_name"], S["wi_why"]
        review = S["wi_review"] if S["wi_use_review"] else None
        try:
            con = decision_log.open_log(wu.log_path())
            ent = wu.make_entry(
                name, wu.sentence(answers), (event,), wu.CARDS[card_key][3], res, choice, why,
                review.isoformat() if review else None,
            )  # fmt: skip
            S["wi_saved"] = decision_log.append(con, ent)
            S.pop("wi_error", None)
        except ValueError as e:
            S["wi_error"] = str(e)

    if S.get("wi_error"):
        st.error(S["wi_error"])
    cols = st.columns([1, 1, 1, 2])
    cols[0].button("Back", on_click=go, args=(4,), key="b6", use_container_width=True)
    cols[1].button("Save decision", type="primary", on_click=save, key="save", use_container_width=True)
    cols[2].button("Start a new test", on_click=start_over, key="new", use_container_width=True)
    st.caption("Saved decisions stay on this computer only. Open them under Past what-if consultations in the menu.")
else:
    start_over()
    st.rerun()
