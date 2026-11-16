"""End-to-end through both domains via the Flask test client."""

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return create_app().test_client()


@pytest.fixture
def jacket(client):
    """A style with one graded POM: chest 52.0 at M, 54.0 at L, tolerance 1.0."""
    response = client.post("/styles", data={
        "code": "JK-014", "name": "Wool blazer", "sizes": "S, M, L", "base_size": "M"})
    url = response.headers["Location"]
    client.post(f"{url}/poms", data={
        "code": "CH", "description": "Chest", "base_value_cm": "52", "tolerance_cm": "1"})
    client.post(f"{url}/poms/1/rules", data={"inc_M": "2", "inc_L": "2"})
    return url


def record(client, measured_cm, size="L"):
    return client.post("/samples", data={
        "style_id": "1", "size": size, "stage": "fit", "m_CH": measured_cm})


def test_new_round_form_shows_graded_target(client, jacket):
    page = client.get("/samples/new?style_id=1&size=L").data.decode()
    assert "54.0" in page and 'name="m_CH"' in page


def test_new_round_for_unknown_size_is_400(client, jacket):
    assert client.get("/samples/new?style_id=1&size=XXL").status_code == 400


def test_non_numeric_style_id_is_400(client):
    assert client.get("/samples/new?style_id=abc&size=M").status_code == 400


def test_record_round_and_show_verdict(client, jacket):
    response = record(client, "55.5")
    assert response.status_code == 302
    page = client.get(response.headers["Location"]).data.decode()
    assert "Rejected" in page and "+1.5" in page


def test_bad_measurement_rerenders_form(client, jacket):
    response = record(client, "abc")
    assert response.status_code == 400
    assert b"is not a number" in response.data


def test_blank_measurement_rejected(client, jacket):
    response = record(client, "")
    assert response.status_code == 400
    assert b"no measurement for CH" in response.data


def test_record_for_deleted_style_is_400(client, jacket):
    client.post("/styles/1/delete")
    assert record(client, "54").status_code == 400


def test_edited_grade_rule_does_not_change_past_verdict(client, jacket):
    record(client, "54.5")  # target 54.0: passes
    client.post(f"{jacket}/poms/1/rules", data={"inc_M": "2", "inc_L": "3"})  # L becomes 55.0
    page = client.get("/samples/1").data.decode()
    assert "Approved" in page and "54.0" in page


def test_round_survives_style_deletion(client, jacket):
    record(client, "54.5")
    client.post("/styles/1/delete")
    assert b"JK-014" in client.get("/samples").data
    assert client.get("/samples/1").status_code == 200


def test_missing_round_is_404(client):
    assert client.get("/samples/99").status_code == 404