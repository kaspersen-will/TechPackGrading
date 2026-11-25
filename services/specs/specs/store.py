"""SQL Server access for the Specs & Grading service. All lengths are integer mm.

get_graded_spec is the seam: the samples service reads spec values only
through it (over HTTP from Wednesday), never from these tables directly.
"""

from specs.grading import GradingError, grade, validate_size_run

# The tables are defined by migrations/001_init.sql, applied by migrate.py.
# style.id is IDENTITY: sample_round.style_id (the samples service) has no foreign
# key, so a deleted style's id must never be handed to a new style (ADR-3).


class UnknownStyleOrSize(GradingError):
    """get_graded_spec was asked for a style or size that doesn't exist (HTTP 404)."""


def _require_whole_mm(*values):
    # SQLite's STRICT tables rejected 452.5 in an INTEGER column; SQL Server's INT
    # silently truncates it to 452, so the check moved here.
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise GradingError(f"{value!r} is not a whole number of mm")


def create_style(conn, code, name, sizes, base_size):
    validate_size_run(sizes, base_size)
    with conn:
        style_id = conn.execute(
            "INSERT INTO style (code, name, base_size) OUTPUT INSERTED.id VALUES (%s, %s, %s)",
            (code, name, base_size),
        ).fetchone()["id"]
        conn.executemany(
            "INSERT INTO style_size (style_id, label, position) VALUES (%s, %s, %s)",
            [(style_id, label, position) for position, label in enumerate(sizes)],
        )
    return style_id


def add_point_of_measure(conn, style_id, code, description, base_value_mm, tolerance_mm):
    _require_whole_mm(base_value_mm, tolerance_mm)
    if tolerance_mm <= 0:
        raise GradingError("tolerance must be greater than zero")
    with conn:
        return conn.execute(
            "INSERT INTO point_of_measure"
            " (style_id, code, description, base_value_mm, tolerance_mm)"
            " OUTPUT INSERTED.id VALUES (%s, %s, %s, %s, %s)",
            (style_id, code, description, base_value_mm, tolerance_mm),
        ).fetchone()["id"]


def set_grade_rule(conn, pom_id, size_label, increment_mm):
    _require_whole_mm(increment_mm)
    size = conn.execute(
        "SELECT s.id, s.position FROM style_size s"
        " JOIN point_of_measure p ON p.style_id = s.style_id"
        " WHERE p.id = %s AND s.label = %s",
        (pom_id, size_label),
    ).fetchone()
    if size is None:
        raise GradingError(f"size {size_label!r} is not in this point of measure's style")
    if size["position"] == 0:
        raise GradingError("the smallest size has no size below it, so it takes no grade rule")
    # SQL Server has no INSERT OR REPLACE: update the rule, insert it if there was none.
    with conn:
        conn.execute(
            "UPDATE grade_rule SET increment_mm = %s WHERE pom_id = %s AND size_id = %s;"
            " IF @@ROWCOUNT = 0"
            " INSERT INTO grade_rule (pom_id, size_id, increment_mm) VALUES (%s, %s, %s);",
            (increment_mm, pom_id, size["id"], pom_id, size["id"], increment_mm),
        )


def get_graded_spec(conn, style_id, size_label):
    """Return every point of measure of a style, graded to one size.

    Shape: {"style_code": str, "poms": [{pom_id, code, description,
    target_mm, tolerance_mm}, ...]}. style_code is included so Domain 2 can
    snapshot it and still label a round after the style is deleted.
    """
    positions = conn.execute(
        "SELECT st.code AS style_code,"
        " target.position AS target_position, base.position AS base_position"
        " FROM style st"
        " JOIN style_size target ON target.style_id = st.id AND target.label = %s"
        " JOIN style_size base ON base.style_id = st.id AND base.label = st.base_size"
        " WHERE st.id = %s",
        (size_label, style_id),
    ).fetchone()

    if positions is None:
        raise UnknownStyleOrSize(f"style {style_id} has no size {size_label!r}")

    rules = conn.execute(
        "SELECT r.pom_id, s.position, r.increment_mm FROM grade_rule r"
        " JOIN style_size s ON s.id = r.size_id"
        " WHERE s.style_id = %s",
        (style_id,),
    ).fetchall()

    increments_by_pom = {}
    for rule in rules:
        increments_by_pom.setdefault(rule["pom_id"], {})[rule["position"]] = rule["increment_mm"]

    poms = conn.execute(
        "SELECT id, code, description, base_value_mm, tolerance_mm"
        " FROM point_of_measure WHERE style_id = %s ORDER BY code",
        (style_id,),
    ).fetchall()

    graded = [
        {
            "pom_id": pom["id"],
            "code": pom["code"],
            "description": pom["description"],
            "target_mm": grade(
                pom["base_value_mm"],
                positions["base_position"],
                positions["target_position"],
                increments_by_pom.get(pom["id"], {}),
            ),
            "tolerance_mm": pom["tolerance_mm"],
        }
        for pom in poms
    ]
    return {"style_code": positions["style_code"], "poms": graded}

# ---- Read/delete functions for Domain 1's own pages. ----
# The samples service's only entry point is get_graded_spec.


def list_styles(conn):
    return conn.execute("SELECT id, code, name, base_size FROM style ORDER BY code").fetchall()


def get_style(conn, style_id):
    """Everything the style page shows, or None if the style doesn't exist.

    rules maps pom_id -> {size label: increment_mm}.
    size_run maps pom_id -> {size label: target_mm, or None if a rule is missing}.
    """
    style = conn.execute(
        "SELECT id, code, name, base_size FROM style WHERE id = %s", (style_id,)
    ).fetchone()
    if style is None:
        return None

    sizes = conn.execute(
        "SELECT label, position FROM style_size WHERE style_id = %s ORDER BY position",
        (style_id,),
    ).fetchall()
    poms = conn.execute(
        "SELECT id, code, description, base_value_mm, tolerance_mm"
        " FROM point_of_measure WHERE style_id = %s ORDER BY code",
        (style_id,),
    ).fetchall()
    rule_rows = conn.execute(
        "SELECT r.pom_id, s.label, s.position, r.increment_mm FROM grade_rule r"
        " JOIN style_size s ON s.id = r.size_id WHERE s.style_id = %s",
        (style_id,),
    ).fetchall()

    rules = {pom["id"]: {} for pom in poms}
    by_position = {pom["id"]: {} for pom in poms}
    for row in rule_rows:
        rules[row["pom_id"]][row["label"]] = row["increment_mm"]
        by_position[row["pom_id"]][row["position"]] = row["increment_mm"]

    base_position = next(s["position"] for s in sizes if s["label"] == style["base_size"])
    size_run = {}
    for pom in poms:
        size_run[pom["id"]] = {}
        for size in sizes:
            try:
                target = grade(pom["base_value_mm"], base_position, size["position"],
                               by_position[pom["id"]])
            except GradingError:
                target = None
            size_run[pom["id"]][size["label"]] = target

    return {"style": style, "sizes": sizes, "poms": poms, "rules": rules, "size_run": size_run}


def delete_style(conn, style_id):
    """Delete a style with its sizes, POMs and grade rules, in one transaction.

    The grade rules go first: only their point-of-measure key cascades (see
    001_init.sql), so deleting the sizes would otherwise be blocked. Knows
    nothing about sample rounds: the samples service copes with its own leftovers.
    Returns False if there was no such style.
    """
    with conn:
        conn.execute(
            "DELETE r FROM grade_rule AS r"
            " JOIN point_of_measure AS p ON p.id = r.pom_id WHERE p.style_id = %s",
            (style_id,),
        )
        deleted = conn.execute("DELETE FROM style WHERE id = %s", (style_id,)).rowcount
    return deleted == 1
