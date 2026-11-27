"""Connection settings and retry, with the driver replaced by a fake: no database needed."""

import pymssql
import pytest

import db

URL = "mssql://samples_user:p%40ss@mssql:1433/samples"


def test_parse_url():
    assert db.parse_url(URL) == {
        "server": "mssql", "port": "1433", "user": "samples_user",
        "password": "p@ss", "database": "samples",
    }


def test_parse_url_default_port():
    assert db.parse_url("mssql://u:p@host/samples")["port"] == "1433"


def test_parse_url_rejects_other_schemes():
    with pytest.raises(ValueError):
        db.parse_url("sqlite:///specs.db")


class FakeClock:
    def __init__(self):
        self.now, self.sleeps = 0.0, []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def __call__(self):
        return self.now


def flaky_driver(failures, error=(40613, b"Database is not currently available")):
    calls = []

    def driver(**settings):
        calls.append(settings)
        if len(calls) <= failures:
            raise pymssql.OperationalError(*error)
        return object()
    return driver, calls


def test_connect_retries_with_backoff_until_database_answers():
    clock = FakeClock()
    driver, calls = flaky_driver(failures=4)
    conn = db.connect(URL, timeout_s=90, sleep=clock.sleep, clock=clock, driver=driver)
    assert isinstance(conn, db.Connection)
    assert len(calls) == 5
    assert clock.sleeps == [1, 2, 4, 8]


def test_backoff_is_capped_and_gives_up_at_the_deadline():
    clock = FakeClock()
    driver, _ = flaky_driver(failures=100)
    with pytest.raises(pymssql.OperationalError):
        db.connect(URL, timeout_s=60, sleep=clock.sleep, clock=clock, driver=driver)
    assert max(clock.sleeps) == 10
    assert sum(clock.sleeps) <= 60


def test_wrong_password_is_not_retried():
    clock = FakeClock()
    driver, calls = flaky_driver(failures=1, error=(18456, b"Login failed for user 'samples_user'."))
    with pytest.raises(pymssql.OperationalError):
        db.connect(URL, timeout_s=90, sleep=clock.sleep, clock=clock, driver=driver)
    assert len(calls) == 1 and clock.sleeps == []
