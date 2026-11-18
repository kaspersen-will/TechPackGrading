import pymssql
import pytest
from conftest import count

import migrate


def write(directory, name, sql):
    (directory / name).write_text(sql, encoding="utf-8")


# ---- Pure checks on the files, no database. ----

def test_migrations_sorted_by_number(tmp_path):
    write(tmp_path, "002_b.sql", "SELECT 2")
    write(tmp_path, "001_a.sql", "SELECT 1")
    assert [m[0] for m in migrate.read_migrations(tmp_path)] == ["001_a.sql", "002_b.sql"]


def test_badly_named_migration_rejected(tmp_path):
    # "10_x.sql" would sort before "9_x.sql"; three digits keep the order right.
    write(tmp_path, "1_init.sql", "SELECT 1")
    with pytest.raises(migrate.MigrationError):
        migrate.read_migrations(tmp_path)


def test_pending_skips_applied(tmp_path):
    write(tmp_path, "001_a.sql", "SELECT 1")
    write(tmp_path, "002_b.sql", "SELECT 2")
    files = migrate.read_migrations(tmp_path)
    applied = {"001_a.sql": files[0][2]}
    assert [m[0] for m in migrate.pending(files, applied)] == ["002_b.sql"]


def test_edited_migration_stops_startup(tmp_path):
    write(tmp_path, "001_a.sql", "SELECT 1")
    files = migrate.read_migrations(tmp_path)
    with pytest.raises(migrate.MigrationError, match="edited"):
        migrate.pending(files, {"001_a.sql": "0" * 64})


def test_missing_migration_file_stops_startup(tmp_path):
    with pytest.raises(migrate.MigrationError, match="missing"):
        migrate.pending([], {"001_a.sql": "0" * 64})


def test_shipped_migrations_are_valid():
    assert migrate.read_migrations()[0][0] == "001_init.sql"


# ---- Against SQL Server. The conn fixture has already applied every migration. ----

def test_second_start_applies_nothing(conn):
    assert migrate.migrate(conn) == []


def test_new_migration_keeps_existing_rows(conn, tmp_path):
    for version, sql, _ in migrate.read_migrations():
        write(tmp_path, version, sql)
    with conn:
        conn.execute("INSERT INTO sample_round (style_id, style_code, size_label, stage)"
                     " VALUES (1, 'JK-1', 'M', 'fit')")
    write(tmp_path, "999_add_note.sql",
          "ALTER TABLE sample_round ADD note NVARCHAR(100) NOT NULL"
          " CONSTRAINT df_sample_round_note DEFAULT N'none';")
    assert migrate.migrate(conn, tmp_path) == ["999_add_note.sql"]
    row = conn.execute("SELECT style_code, note FROM sample_round").fetchone()
    assert row == {"style_code": "JK-1", "note": "none"}
    assert count(conn, "schema_migrations") == 2


def test_failed_migration_leaves_nothing_behind(conn, tmp_path):
    for version, sql, _ in migrate.read_migrations():
        write(tmp_path, version, sql)
    write(tmp_path, "999_broken.sql",
          "CREATE TABLE half_done (id INT); SELECT * FROM no_such_table;")
    with pytest.raises(pymssql.DatabaseError):
        migrate.migrate(conn, tmp_path)
    assert conn.execute("SELECT OBJECT_ID(N'half_done') AS id").fetchone()["id"] is None
    assert count(conn, "schema_migrations") == 1
