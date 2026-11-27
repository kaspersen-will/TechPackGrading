"""Apply migrations/NNN_name.sql in order, each exactly once. Forward only.

Run before the web server starts (python migrate.py), never inside it, so
several web workers can't race to apply the same migration.

schema_migrations records every applied file with a checksum. A file that
changed after it was applied stops startup: corrections go in a new migration.
"""

import hashlib
import logging
import os
import re
import sys
from pathlib import Path

import db

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
NAME = re.compile(r"^\d{3}_[a-z0-9_]+\.sql$")

TRACKING_TABLE = """
IF OBJECT_ID(N'dbo.schema_migrations', N'U') IS NULL
    CREATE TABLE dbo.schema_migrations (
        version    NVARCHAR(100) NOT NULL CONSTRAINT pk_schema_migrations PRIMARY KEY,
        checksum   CHAR(64)      NOT NULL,
        applied_at DATETIME2(0)  NOT NULL
            CONSTRAINT df_schema_migrations_applied_at DEFAULT SYSUTCDATETIME()
    );
"""

log = logging.getLogger("migrate")


class MigrationError(Exception):
    pass


def read_migrations(directory=MIGRATIONS_DIR):
    """[(version, sql, checksum)] sorted by version. Rejects names that would sort wrongly."""
    migrations = []
    for path in sorted(Path(directory).glob("*.sql")):
        if not NAME.match(path.name):
            raise MigrationError(f"{path.name}: migration files are named NNN_snake_case.sql")
        sql = path.read_text(encoding="utf-8")
        migrations.append((path.name, sql, hashlib.sha256(sql.encode("utf-8")).hexdigest()))
    return migrations


def pending(migrations, applied):
    """The migrations still to run. applied maps version -> checksum recorded in the database."""
    known = {version for version, _, _ in migrations}
    for version in applied:
        if version not in known:
            raise MigrationError(f"{version} is applied in the database but its file is missing")
    for version, _, checksum in migrations:
        if version in applied and applied[version] != checksum:
            raise MigrationError(f"{version} was edited after it was applied; add a new migration instead")
    return [m for m in migrations if m[0] not in applied]


def migrate(conn, directory=MIGRATIONS_DIR):
    """Apply pending migrations, each in its own transaction. Returns the versions applied."""
    with conn:
        conn.execute(TRACKING_TABLE)
    applied = {row["version"]: row["checksum"]
               for row in conn.execute("SELECT version, checksum FROM dbo.schema_migrations")}
    todo = pending(read_migrations(directory), applied)
    for version, sql, checksum in todo:
        # SQL Server DDL is transactional: a failing migration leaves no half-built tables
        # and no schema_migrations row, so the next start tries it again.
        with conn:
            conn.execute(sql)
            conn.execute("INSERT INTO dbo.schema_migrations (version, checksum) VALUES (%s, %s)",
                         (version, checksum))
        log.info("applied migration %s", version)
    if not todo:
        log.info("schema up to date, %d migrations already applied", len(applied))
    return [version for version, _, _ in todo]


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    conn = db.connect(url)
    try:
        migrate(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
