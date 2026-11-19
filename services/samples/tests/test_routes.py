"""The cross-seam flow end to end: samples' real API and database, specs replaced
by a stub HTTP server (tests/stub_specs.py). DB tests skip without TEST_DATABASE_URL;
the specs-down and bad-input cases need no database and always run.
"""

import pytest
from stub_specs import nothing_listening, specs  # noqa: F401 (fixtures)

from app import create_app

ROUND = {"style_id": 1, "size": "L", "stage": "fit", "measured_mm": {"CH": 555}}


def make_client(monkeypatch, database_url, specs_url):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SPECS_URL", specs_url)
    monkeypatch.setenv("SPECS_TIMEOUT_S", "1")
    return create_app().test_client()


@pytest.fixture
def client(database_url, specs, monkeypatch):  # noqa: F811
    return make_client(monkeypatch, database_url, specs[1])


# ---- No database: the request is answered before samples opens a connection. ----

NO_DB = "mssql://u:p@127.0.0.1:1/nothing_test"


def test_specs_down_is_a_clear_503_and_saves_nothing(monkeypatch, nothing_listening):  # noqa: F811
    client = make_client(monkeypatch, NO_DB, nothing_listening)
    response = client.post("/rounds", json=ROUND)
    assert response.status_code == 503
    assert "specs service is not responding" in response.get_json()["error"]


def test_unknown_size_in_specs_is_422(monkeypatch, specs):  # noqa: F811
    stub, url = specs
    stub.answer(404, {"error": "style 1 has no size 'XXL'"})
    response = make_client(monkeypatch, NO_DB, url).post("/rounds", json={**ROUND, "size": "XXL"})
    assert response.status_code == 422
    assert response.get_json() == {"error": "style 1 has no size 'XXL'"}


@pytest.mark.parametrize("change", [
    {"style_id": "1"}, {"size": ""}, {"stage": "final"},
    {"measured_mm": {"CH": "55.5"}}, {"measured_mm": {"CH": 55.5}}, {"measured_mm": []},
])
def test_bad_body_is_400_without_calling_specs(monkeypatch, specs, change):  # noqa: F811
    stub, url = specs
    response = make_client(monkeypatch, NO_DB, url).post("/rounds", json={**ROUND, **change})
    assert response.status_code == 400
    assert stub.requests == []


# ---- With the samples test database. ----

def test_health_writes_to_own_database(client):
    assert client.get("/health").get_json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_record_round_snapshots_the_spec_and_shows_verdict(client, specs):  # noqa: F811
    response = client.post("/rounds", json=ROUND)
    assert response.status_code == 201
    body = client.get(response.headers["Location"]).get_json()
    assert body["round"]["style_code"] == "JK-014"
    [row] = body["measurements"]
    assert row["target_mm"] == 540 and row["deviation_mm"] == 15 and row["passes"] is False
    assert body["summary"] == {"total": 1, "failed": 1, "failed_codes": ["CH"], "approved": False}
    assert specs[0].requests == ["/styles/1/spec/L"]


def test_recorded_rounds_still_show_when_specs_is_down(client, specs):  # noqa: F811
    round_id = client.post("/rounds", json=ROUND).get_json()["id"]
    specs[0].answer(503, {"status": "unavailable"})
    assert client.get(f"/rounds/{round_id}").status_code == 200
    [listed] = client.get("/rounds").get_json()
    assert listed["id"] == round_id and listed["recorded_at"].endswith("Z")
    assert client.post("/rounds", json=ROUND).status_code == 503


def test_missing_measurement_saves_nothing(client):
    response = client.post("/rounds", json={**ROUND, "measured_mm": {}})
    assert response.status_code == 400
    assert response.get_json() == {"error": "no measurement for CH"}
    assert client.get("/rounds").get_json() == []


def test_missing_round_is_404(client):
    assert client.get("/rounds/999").status_code == 404
