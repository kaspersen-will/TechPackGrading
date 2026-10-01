"""Domain 2's store, tested with only its own schema and a hand-built spec.

No specs tables exist in this database: proof that Sample Fit Review
works without Domain 1's storage.
"""

import pytest

import db
from samples.review import SampleError
from samples.store import SCHEMA, get_round, list_rounds, record_round

SPEC = {
    "style_code": "FW26-JKT-014",
    "poms": [
        {"pom_id": 1, "code": "BL", "description": "Body length", "target_mm": 720, "tolerance_mm": 15},
        {"pom_id": 2, "code": "CH", "description": "Chest", "target_mm": 520, "tolerance_mm": 10},
    ],
}


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path, [SCHEMA])
    connection = db.get_connection(path)
    yield connection
    connection.close()


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_record_and_read_round(conn):
    round_id = record_round(conn, 7, "M", "fit", SPEC, {"BL": 722, "CH": 535})
    data = get_round(conn, round_id)
    assert data["round"]["style_code"] == "FW26-JKT-014"
    assert data["round"]["style_id"] == 7
    assert [m["pom_code"] for m in data["measurements"]] == ["BL", "CH"]
    assert data["summary"] == {"total": 2, "failed": 1, "failed_codes": ["CH"], "approved": False}


def test_rejected_submission_writes_nothing(conn):
    with pytest.raises(SampleError):
        record_round(conn, 7, "M", "fit", SPEC, {"BL": 722})
    assert count(conn, "sample_round") == 0
    assert count(conn, "round_measurement") == 0


def test_unknown_stage_rejected(conn):
    with pytest.raises(SampleError, match="stage must be one of"):
        record_round(conn, 7, "M", "final", SPEC, {"BL": 722, "CH": 520})
    assert count(conn, "sample_round") == 0


def test_get_missing_round_is_none(conn):
    assert get_round(conn, 99) is None


def test_list_rounds_newest_first_with_summaries(conn):
    first = record_round(conn, 7, "M", "proto", SPEC, {"BL": 720, "CH": 520})
    second = record_round(conn, 7, "L", "fit", SPEC, {"BL": 700, "CH": 520})
    rounds = list_rounds(conn)
    assert [r["round"]["id"] for r in rounds] == [second, first]
    assert rounds[0]["summary"]["approved"] is False
    assert rounds[1]["summary"]["approved"] is True


def test_list_rounds_empty(conn):
    assert list_rounds(conn) == []