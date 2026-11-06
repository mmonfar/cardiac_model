"""Decision log (station 3): append-only, CSV export, no UPDATE or DELETE."""

import pathlib
import re
import sqlite3

import pytest

from cardiac_capacity import decision_log as dl


def entry(**kw: object) -> dl.Entry:
    base: dict[str, object] = dict(
        asker="Demo manager", question="3 beds blocked from week 2?", events=[{"kind": "block_beds", "amount": 3}],
        model_version="2.2.3", parameter_set="literature", seeds="500-529",
        results={"baseline": {"list_end": 60}, "scenario": {"list_end": 72}},
        decision_choice="Add one extra list", decision_by="Demo lead", decision_why="Keeps the list stable.",
    )  # fmt: skip
    base.update(kw)
    return dl.Entry(**base)  # type: ignore[arg-type]


@pytest.fixture()
def con(tmp_path: pathlib.Path) -> sqlite3.Connection:
    return dl.open_log(str(tmp_path / "log.db"))


def test_append_and_read(con: sqlite3.Connection) -> None:
    i = dl.append(con, entry())
    assert i == 1 and dl.get(con, 1)["decision_choice"] == "Add one extra list"
    assert dl.get(con, 1)["utc_time"].endswith("Z")


def test_update_and_delete_are_refused(con: sqlite3.Connection) -> None:
    dl.append(con, entry())
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("UPDATE consultation SET asker = 'x'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("DELETE FROM consultation")
    assert len(dl.rows(con)) == 1


def test_correction_is_a_new_row(con: sqlite3.Connection) -> None:
    dl.append(con, entry())
    j = dl.append(con, entry(decision_why="Corrected reason.", corrects_id=1))
    assert j == 2 and dl.get(con, 2)["corrects_id"] == 1
    assert dl.get(con, 1)["decision_why"] == "Keeps the list stable."
    with pytest.raises(ValueError, match="does not exist"):
        dl.append(con, entry(corrects_id=99))


def test_blank_fields_and_bad_values_refused(con: sqlite3.Connection) -> None:
    for bad in (dict(asker=" "), dict(decision_why=""), dict(level="big"), dict(review_date="31/12/2026")):
        with pytest.raises(ValueError):
            dl.append(con, entry(**bad))
    assert dl.rows(con) == []


def test_csv_export_has_disclaimer_header_and_rows(con: sqlite3.Connection) -> None:
    dl.append(con, entry(review_date="2026-12-31"))
    lines = dl.export_csv(con).splitlines()
    assert "Not a medical device" in lines[0]
    assert lines[1].split(",")[0] == "id" and len(lines) == 3
    assert "2026-12-31" in lines[2]


def test_print_view_has_disclaimer(con: sqlite3.Connection) -> None:
    dl.append(con, entry())
    v = dl.print_view(con, 1)
    assert "Not a medical device" in v and "Demo lead" in v


def test_code_has_no_update_or_delete_statements() -> None:
    src = pathlib.Path(dl.__file__).read_text()
    code = re.sub(r'_SCHEMA = """.*?"""', "", src, flags=re.S)
    assert not re.search(r"\b(UPDATE|DELETE|DROP)\b", code, flags=re.I)
