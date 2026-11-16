"""SQLite access for the Sample Fit Review domain. All lengths are integer mm.

This module never imports specs and never reads its tables. The caller
hands in the graded spec (the result of get_graded_spec), and the values
are copied into this domain's own rows.
"""

from samples.review import STAGES, SampleError, build_measurements, review, summarise

# style_id deliberately has no REFERENCES: style lives in the other domain (ADR-3).
# round_measurement -> sample_round is a foreign key inside this domain, which is fine.
SCHEMA = """
CREATE TABLE IF NOT EXISTS sample_round (
    id          INTEGER PRIMARY KEY,
    style_id    INTEGER NOT NULL,
    style_code  TEXT NOT NULL,
    size_label  TEXT NOT NULL,
    stage       TEXT NOT NULL CHECK (stage IN ('proto', 'fit', 'pre-production')),
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
) STRICT;

CREATE TABLE IF NOT EXISTS round_measurement (
    round_id     INTEGER NOT NULL REFERENCES sample_round(id) ON DELETE CASCADE,
    pom_code     TEXT NOT NULL,
    description  TEXT NOT NULL,
    target_mm    INTEGER NOT NULL,
    tolerance_mm INTEGER NOT NULL,
    measured_mm  INTEGER NOT NULL,
    PRIMARY KEY (round_id, pom_code)
) STRICT;
"""


def record_round(conn, style_id, size_label, stage, spec, measured_by_code):
    """Snapshot the graded spec and the factory's values as one round.

    Everything is validated before the first INSERT, and all inserts run in
    one transaction, so a rejected submission writes nothing.
    """
    if stage not in STAGES:
        raise SampleError(f"stage must be one of {', '.join(STAGES)}")
    rows = build_measurements(spec["poms"], measured_by_code)

    with conn:
        cur = conn.execute(
            "INSERT INTO sample_round (style_id, style_code, size_label, stage)"
            " VALUES (?, ?, ?, ?)",
            (style_id, spec["style_code"], size_label, stage),
        )
        round_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO round_measurement"
            " (round_id, pom_code, description, target_mm, tolerance_mm, measured_mm)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [(round_id, r["pom_code"], r["description"], r["target_mm"],
              r["tolerance_mm"], r["measured_mm"]) for r in rows],
        )
    return round_id


def _measurements(conn, round_ids):
    """Reviewed measurement rows grouped by round id."""
    grouped = {round_id: [] for round_id in round_ids}
    if not round_ids:
        return grouped
    placeholders = ", ".join("?" for _ in round_ids)
    rows = conn.execute(
        "SELECT round_id, pom_code, description, target_mm, tolerance_mm, measured_mm"
        f" FROM round_measurement WHERE round_id IN ({placeholders}) ORDER BY pom_code",
        list(round_ids),
    ).fetchall()
    for row in rows:
        grouped[row["round_id"]].append(review(dict(row)))
    return grouped


def list_rounds(conn):
    """Every round, newest first, each with its summary."""
    rounds = conn.execute(
        "SELECT id, style_id, style_code, size_label, stage, recorded_at"
        " FROM sample_round ORDER BY id DESC"
    ).fetchall()
    measurements = _measurements(conn, [r["id"] for r in rounds])
    return [{"round": r, "summary": summarise(measurements[r["id"]])} for r in rounds]


def get_round(conn, round_id):
    """One round with its reviewed measurements and summary, or None."""
    sample_round = conn.execute(
        "SELECT id, style_id, style_code, size_label, stage, recorded_at"
        " FROM sample_round WHERE id = ?",
        (round_id,),
    ).fetchone()
    if sample_round is None:
        return None
    reviewed = _measurements(conn, [round_id])[round_id]
    return {"round": sample_round, "measurements": reviewed, "summary": summarise(reviewed)}