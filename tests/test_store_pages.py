import pytest

import db
from specs.store import (
    SCHEMA, add_point_of_measure, create_style, delete_style, get_graded_spec,
    get_style, list_styles, set_grade_rule,
)
from specs.grading import GradingError


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path, [SCHEMA])
    conn = db.get_connection(path)
    yield conn
    conn.close()


@pytest.fixture
def jacket(conn):
    style_id = create_style(conn, "JK-014", "Wool blazer", ["XS", "S", "M", "L", "XL"], "M")
    chest = add_point_of_measure(conn, style_id, "CH", "Chest", 520, 10)
    for size, increment in [("S", 15), ("M", 20), ("L", 20), ("XL", 25)]:
        set_grade_rule(conn, chest, size, increment)
    return style_id, chest


def test_list_styles_sorted_by_code(conn):
    create_style(conn, "ZZ-1", "Coat", ["M"], "M")
    create_style(conn, "AA-1", "Shirt", ["M"], "M")
    assert [s["code"] for s in list_styles(conn)] == ["AA-1", "ZZ-1"]


def test_get_style_missing_returns_none(conn):
    assert get_style(conn, 999) is None


def test_get_style_full_size_run(conn, jacket):
    style_id, chest = jacket
    data = get_style(conn, style_id)
    assert [s["label"] for s in data["sizes"]] == ["XS", "S", "M", "L", "XL"]
    assert data["rules"][chest] == {"S": 15, "M": 20, "L": 20, "XL": 25}
    assert data["size_run"][chest] == {"XS": 485, "S": 500, "M": 520, "L": 540, "XL": 565}


def test_get_style_marks_only_unreachable_sizes_missing(conn, jacket):
    # Sleeve has rules for L and XL only: sizes above base grade, sizes below can't.
    style_id, _ = jacket
    sleeve = add_point_of_measure(conn, style_id, "SL", "Sleeve", 640, 10)
    set_grade_rule(conn, sleeve, "L", 10)
    set_grade_rule(conn, sleeve, "XL", 10)
    run = get_style(conn, style_id)["size_run"][sleeve]
    assert run == {"XS": None, "S": None, "M": 640, "L": 650, "XL": 660}


def test_get_style_matches_seam(conn, jacket):
    # Page and seam must agree, or Domain 1 would show one number and Domain 2 check another.
    style_id, chest = jacket
    run = get_style(conn, style_id)["size_run"][chest]
    for label, target in run.items():
        assert get_graded_spec(conn, style_id, label)["poms"][0]["target_mm"] == target


def test_delete_style_cascades_inside_domain_1(conn, jacket):
    style_id, _ = jacket
    assert delete_style(conn, style_id) is True
    for table in ("style", "style_size", "point_of_measure", "grade_rule"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_delete_style_then_seam_raises(conn, jacket):
    # This is what Domain 2 will see for an orphaned round.
    style_id, _ = jacket
    delete_style(conn, style_id)
    with pytest.raises(GradingError):
        get_graded_spec(conn, style_id, "M")


def test_seam_style_without_poms(conn):
    style_id = create_style(conn, "EMPTY-1", "Blank", ["S", "M"], "M")
    assert get_graded_spec(conn, style_id, "S") == {"style_code": "EMPTY-1", "poms": []}


def test_delete_missing_style(conn):
    assert delete_style(conn, 999) is False