"""SQL Server access for this service. Copied, not shared, between the two services.

DATABASE_URL looks like mssql://user:password@host:1433/database.
connect() returns a thin wrapper over a pymssql connection so the store keeps
the shape it had with sqlite3: conn.execute(...) returns a cursor, and
`with conn:` commits on success and rolls back on an exception.
"""

import logging
import os
import time
from urllib.parse import unquote, urlsplit

import pymssql

# Routes catch this for duplicate codes and unknown parents (SQL Server errors 2627, 2601, 547).
IntegrityError = pymssql.IntegrityError

log = logging.getLogger(__name__)

LOGIN_FAILED = 18456  # wrong user or password: waiting won't fix it


def parse_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("mssql", "mssql+pymssql") or not parts.hostname:
        raise ValueError("DATABASE_URL must look like mssql://user:password@host:1433/database")
    return {
        "server": parts.hostname,
        "port": str(parts.port or 1433),
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": parts.path.lstrip("/"),
    }


class Connection:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=None):
        # Rows come back as dicts, so row["code"] works as it did with sqlite3.Row.
        cursor = self._raw.cursor(as_dict=True)
        cursor.execute(sql, tuple(params) if params else None)
        return cursor

    def executemany(self, sql, rows):
        cursor = self._raw.cursor()
        cursor.executemany(sql, [tuple(row) for row in rows])
        return cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._raw.commit()
        else:
            self._raw.rollback()
        return False

    def close(self):
        self._raw.close()


def connect(url, timeout_s=None, sleep=time.sleep, clock=time.monotonic, driver=pymssql.connect):
    """Open a connection, retrying with backoff while the database is unreachable.

    An Azure serverless database that auto-paused takes up to about a minute to
    resume and refuses connections meanwhile (error 40613); locally, SQL Server
    takes a while to start. A wrong password is not retried.
    """
    if timeout_s is None:
        timeout_s = float(os.environ.get("DB_CONNECT_TIMEOUT_S", "90"))
    settings = parse_url(url)
    deadline = clock() + timeout_s
    delay, attempt = 1.0, 1
    while True:
        try:
            raw = driver(**settings, login_timeout=10, timeout=30, tds_version="7.4",
                         autocommit=False)
            return Connection(raw)
        except pymssql.OperationalError as error:
            if LOGIN_FAILED in _error_codes(error) or clock() + delay > deadline:
                raise
            log.warning("database not reachable (attempt %d), retrying in %.0fs: %s",
                        attempt, delay, _first_line(error))
            sleep(delay)
            delay, attempt = min(delay * 2, 10.0), attempt + 1


def _error_codes(error):
    return {arg for arg in error.args if isinstance(arg, int)} | {
        arg[0] for arg in error.args if isinstance(arg, tuple) and arg and isinstance(arg[0], int)
    }


def _first_line(error):
    return str(error).splitlines()[0][:200] if str(error) else type(error).__name__
