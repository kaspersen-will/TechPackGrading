"""Fixtures for tests that need SQL Server.

They run against TEST_DATABASE_URL, a throwaway database (samples_test locally,
created by db/init.sql), never the service's real one. Without it they are
skipped, so the pure-logic tests still run anywhere.
"""

import os

import pytest

import db
import migrate

# Tests only: wipe the test database so every test starts from the migrations.
# The service itself never drops anything.
DROP_EVERYTHING = """
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += N'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + N'.'
    + QUOTENAME(OBJECT_NAME(parent_object_id)) + N' DROP CONSTRAINT ' + QUOTENAME(name) + N';'
FROM sys.foreign_keys;
SELECT @sql += N'DROP TABLE ' + QUOTENAME(SCHEMA_NAME(schema_id)) + N'.' + QUOTENAME(name) + N';'
FROM sys.tables;
EXEC sp_executesql @sql;
"""


@pytest.fixture
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; start SQL Server with docker compose (README)")
    if not db.parse_url(url)["database"].endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point at a *_test database: the tests wipe it")
    conn = db.connect(url, timeout_s=30)
    try:
        with conn:
            conn.execute(DROP_EVERYTHING)
        migrate.migrate(conn)
    finally:
        conn.close()
    return url


@pytest.fixture
def conn(database_url):
    connection = db.connect(database_url)
    yield connection
    connection.close()


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
