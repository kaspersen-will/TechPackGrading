"""Logging, CORS, JSON errors and /health failing, all without a database.

DATABASE_URL points at a port where nothing listens, so any route that
connects fails the way it would with SQL Server down.
"""

import logging

import pytest

from app import create_app

UI = "http://localhost:8080"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@127.0.0.1:1/nothing_test")
    monkeypatch.setenv("UI_ORIGIN", UI)
    monkeypatch.setenv("HEALTH_DB_TIMEOUT_S", "0")  # one attempt, no retry
    monkeypatch.setenv("GIT_SHA", "abc123")
    return create_app().test_client()


def test_health_is_503_when_database_is_down(client):
    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable", "db": "error", "version": "abc123"}


def test_unknown_path_is_json_404(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_bad_body_rejected_before_touching_the_database(client):
    response = client.post("/styles", data="not json")
    assert response.status_code == 400
    assert response.get_json() == {"error": "the body must be a JSON object"}


def test_cors_allows_the_ui_origin_only(client):
    allowed = client.get("/nope", headers={"Origin": UI})
    assert allowed.headers["Access-Control-Allow-Origin"] == UI
    other = client.get("/nope", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in other.headers
    assert "Origin" in other.headers["Vary"]


def test_preflight_for_json_post(client):
    response = client.options("/styles", headers={
        "Origin": UI, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type"})
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == UI
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    assert response.headers["Access-Control-Allow-Headers"] == "Content-Type"


def test_one_log_line_per_request(client, caplog):
    with caplog.at_level(logging.INFO, logger="request"):
        client.get("/nope")
    [line] = [r.getMessage() for r in caplog.records if r.name == "request"]
    assert line.startswith("GET /nope 404 ") and line.endswith("ms")


def test_database_down_on_a_route_is_json_500_not_a_stack_trace(client, monkeypatch):
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_S", "0")
    response = client.get("/styles")
    assert response.status_code == 500
    assert response.get_json() == {"error": "internal error"}
