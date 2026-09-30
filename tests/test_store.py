import sqlite3

import pytest

import db
from specs.grading import GradingError
from specs.store import (
    SCHEMA,
    add_point_of_measure,
    create_style,
    get_graded_spec,
    set_grade_rule,
)


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path, [SCHEMA])
    connection = db.get_connection(path)
    yield connection
    connection.close()


@pytest.fixture
def jacket(conn):
    style_id = create_style(conn, "FW26-JKT-014", "Wool blazer", ["XS", "S", "M", "L", "XL"], "M")
    chest = add_point_of_measure(conn, style_id, "CH", "Chest, 1 cm below armhole", 520, 10)
    for size, increment in [("S", 15), ("M", 20), ("L", 20), ("XL", 25)]:
        set_grade_rule(conn, chest, size, increment)
    return style_id, chest


def test_init_db_can_run_twice(tmp_path):
    path = tmp_path / "twice.db"
    db.init_db(path, [SCHEMA])
    db.init_db(path, [SCHEMA])


def test_graded_spec_for_each_size(conn, jacket):
    style_id, _ = jacket
    assert get_graded_spec(conn, style_id, "XS")["poms"][0]["target_mm"] == 485
    spec = get_graded_spec(conn, style_id, "XL")
    assert spec == {
    "style_code": "FW26-JKT-014",
    "poms": [
        {
            "pom_id": jacket[1],
            "code": "CH",
            "description": "Chest, 1 cm below armhole",
            "target_mm": 565,
            "tolerance_mm": 10,
        }
    ],
}


def test_graded_spec_unknown_size(conn, jacket):
    with pytest.raises(GradingError, match="no size 'XXL'"):
        get_graded_spec(conn, jacket[0], "XXL")


def test_graded_spec_unknown_style(conn):
    with pytest.raises(GradingError):
        get_graded_spec(conn, 999, "M")


def test_graded_spec_missing_rule(conn, jacket):
    style_id, _ = jacket
    add_point_of_measure(conn, style_id, "SL", "Sleeve length", 640, 10)
    with pytest.raises(GradingError, match="missing grade rule"):
        get_graded_spec(conn, style_id, "L")


def test_set_grade_rule_replaces_existing(conn, jacket):
    style_id, chest = jacket
    set_grade_rule(conn, chest, "XL", 30)
    assert get_graded_spec(conn, style_id, "XL")["poms"][0]["target_mm"] == 570


def test_no_grade_rule_on_smallest_size(conn, jacket):
    with pytest.raises(GradingError, match="smallest size"):
        set_grade_rule(conn, jacket[1], "XS", 10)


def test_no_grade_rule_for_size_of_other_style(conn, jacket):
    create_style(conn, "FW26-TRS-002", "Trouser", ["28", "30", "32"], "30")
    with pytest.raises(GradingError, match="not in this point of measure's style"):
        set_grade_rule(conn, jacket[1], "32", 10)


def test_tolerance_must_be_positive(conn, jacket):
    with pytest.raises(GradingError, match="greater than zero"):
        add_point_of_measure(conn, jacket[0], "HM", "Hem width", 500, 0)


def test_invalid_size_run_writes_nothing(conn):
    with pytest.raises(GradingError):
        create_style(conn, "BAD-1", "Bad", ["S", "M"], "XL")
    assert conn.execute("SELECT COUNT(*) FROM style").fetchone()[0] == 0


def test_duplicate_style_code_rolls_back_sizes(conn, jacket):
    with pytest.raises(sqlite3.IntegrityError):
        create_style(conn, "FW26-JKT-014", "Copy", ["S"], "S")
    assert conn.execute("SELECT COUNT(*) FROM style_size").fetchone()[0] == 5


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        add_point_of_measure(conn, 999, "CH", "Chest", 520, 10)


def test_strict_table_rejects_fractional_mm(conn, jacket):
    with pytest.raises(sqlite3.IntegrityError):
        add_point_of_measure(conn, jacket[0], "SH", "Shoulder", 452.5, 10)

def test_each_point_of_measure_uses_its_own_rules(conn, jacket):
    style_id, _ = jacket
    sleeve = add_point_of_measure(conn, style_id, "SL", "Sleeve length", 640, 10)
    for size, increment in [("S", 5), ("M", 10), ("L", 10), ("XL", 15)]:
        set_grade_rule(conn, sleeve, size, increment)
    graded = get_graded_spec(conn, style_id, "XL")["poms"]
    spec = {row["code"]: row["target_mm"] for row in graded}
    assert spec == {"CH": 565, "SL": 665}
