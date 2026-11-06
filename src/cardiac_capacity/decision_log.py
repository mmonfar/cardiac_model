"""Append-only decision log (station 3): local SQLite, corrections are new rows, never edits.

Synthetic data only in demos. The code has no row-changing or row-removing statements; the table also
refuses them with triggers, so a hand-typed command fails too.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

DISCLAIMER = (
    "Research and demonstration software. Not a medical device and not intended for clinical "
    "decision-making, diagnosis or treatment. Uses synthetic data only. Results are ranges of "
    "possible futures, not a forecast."
)
LEVELS = ("strategic", "tactical", "operational")  # Hulshof et al. 2012 taxonomy

COLUMNS = (
    "id", "utc_time", "asker", "question", "level", "events_json", "model_version", "parameter_set",
    "seeds", "results_json", "decision_choice", "decision_by", "decision_why", "review_date", "corrects_id",
)  # fmt: skip

_SCHEMA = """
CREATE TABLE IF NOT EXISTS consultation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utc_time TEXT NOT NULL,
    asker TEXT NOT NULL,
    question TEXT NOT NULL,
    level TEXT NOT NULL,
    events_json TEXT NOT NULL,
    model_version TEXT NOT NULL,
    parameter_set TEXT NOT NULL,
    seeds TEXT NOT NULL,
    results_json TEXT NOT NULL,
    decision_choice TEXT NOT NULL,
    decision_by TEXT NOT NULL,
    decision_why TEXT NOT NULL,
    review_date TEXT,
    corrects_id INTEGER REFERENCES consultation(id)
);
CREATE TRIGGER IF NOT EXISTS consultation_no_update BEFORE UPDATE ON consultation
BEGIN SELECT RAISE(ABORT, 'The decision log is append-only: add a correcting row instead.'); END;
CREATE TRIGGER IF NOT EXISTS consultation_no_delete BEFORE DELETE ON consultation
BEGIN SELECT RAISE(ABORT, 'The decision log is append-only: add a correcting row instead.'); END;
"""


@dataclass(frozen=True)
class Entry:
    asker: str
    question: str
    events: Any  # JSON-able list of events
    model_version: str
    parameter_set: str
    seeds: str
    results: Any  # JSON-able, shown results with baseline
    decision_choice: str
    decision_by: str
    decision_why: str
    level: str = "tactical"
    review_date: str | None = None
    corrects_id: int | None = None


def open_log(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(_SCHEMA)
    return con


def _need(value: str, what: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"Please fill in: {what}.")
    return value.strip()


def append(con: sqlite3.Connection, e: Entry, now: datetime | None = None) -> int:
    """Add one row and return its id."""
    _need(e.asker, "who asked")
    _need(e.question, "the question")
    _need(e.decision_choice, "the choice")
    _need(e.decision_by, "who decided")
    _need(e.decision_why, "the reason")
    if e.level not in LEVELS:
        raise ValueError(f"Level must be one of: {', '.join(LEVELS)}.")
    if e.review_date is not None:
        try:
            datetime.strptime(e.review_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Review date must look like 2026-12-31.") from None
    if (
        e.corrects_id is not None
        and con.execute("SELECT 1 FROM consultation WHERE id = ?", (e.corrects_id,)).fetchone() is None
    ):
        raise ValueError("The row you want to correct does not exist.")
    t = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = con.execute(
        "INSERT INTO consultation (utc_time, asker, question, level, events_json, model_version, "
        "parameter_set, seeds, results_json, decision_choice, decision_by, decision_why, review_date, "
        "corrects_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            t, e.asker, e.question, e.level, json.dumps(e.events, sort_keys=True), e.model_version,
            e.parameter_set, e.seeds, json.dumps(e.results, sort_keys=True), e.decision_choice,
            e.decision_by, e.decision_why, e.review_date, e.corrects_id,
        ),
    )  # fmt: skip
    con.commit()
    return int(cur.lastrowid or 0)


def rows(con: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = con.execute(f"SELECT {', '.join(COLUMNS)} FROM consultation ORDER BY id")
    return [dict(zip(COLUMNS, r)) for r in cur.fetchall()]


def get(con: sqlite3.Connection, row_id: int) -> dict[str, Any]:
    for r in rows(con):
        if r["id"] == row_id:
            return r
    raise KeyError(row_id)


def export_csv(con: sqlite3.Connection) -> str:
    """CSV text: a disclaimer line first, then the header and every row."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([DISCLAIMER])
    w.writerow(COLUMNS)
    for r in rows(con):
        w.writerow([r[c] for c in COLUMNS])
    return buf.getvalue()


def print_view(con: sqlite3.Connection, row_id: int) -> str:
    """One-page plain text for a governance meeting."""
    r = get(con, row_id)
    lines = (
        f"Consultation {r['id']} ({r['utc_time']})",
        f"Asked by: {r['asker']}",
        f"Question: {r['question']}",
        f"Kind of decision: {r['level']}",
        f"Events: {r['events_json']}",
        f"Model: {r['model_version']}; parameter set: {r['parameter_set']}; seeds: {r['seeds']}",
        f"Results shown: {r['results_json']}",
        f"Decision: {r['decision_choice']} (by {r['decision_by']})",
        f"Reason: {r['decision_why']}",
        f"Review date: {r['review_date'] or 'none set'}",
        f"Corrects row: {r['corrects_id'] if r['corrects_id'] is not None else 'none'}",
        "",
        DISCLAIMER,
    )
    return "\n".join(lines)
