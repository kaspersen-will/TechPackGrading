"""Samples' own routes, with the specs service replaced by a fake get_graded_spec.

The real call across the seam is tested in tests/integration/ at the repo root.
"""

import pytest

from app import create_app
from samples import routes
from samples.specs_client import SpecError

# Chest 54.0 cm at L, tolerance 1.0 cm: what specs would return for JK-014 size L.
SPEC_L = {
    "style_code": "JK-014",
    "poms": [{"pom_id": 1, "code": "CH", "description": "Chest", "target_mm": 540, "tolerance_mm": 10}],
}


def fake_get_graded_spec(style_id, size_label):
    if style_id == 1 and size_label == "L":
        return SPEC_L
    raise SpecError(f"style {style_id} has no size {size_label!r}")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "get_graded_spec", fake_get_graded_spec)
    return create_app().test_client()


def record(client, measured_cm, size="L"):
    return client.post("/samples", data={
        "style_id": "1", "size": size, "stage": "fit", "m_CH": measured_cm})


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_index_redirects_to_rounds(client):
    assert client.get("/").headers["Location"] == "/samples"


def test_new_round_form_shows_graded_target(client):
    page = client.get("/samples/new?style_id=1&size=L").data.decode()
    assert "54.0" in page and 'name="m_CH"' in page


def test_new_round_for_unknown_size_is_400(client):
    assert client.get("/samples/new?style_id=1&size=XXL").status_code == 400


def test_non_numeric_style_id_is_400(client):
    assert client.get("/samples/new?style_id=abc&size=M").status_code == 400


def test_record_round_and_show_verdict(client):
    response = record(client, "55.5")
    assert response.status_code == 302
    page = client.get(response.headers["Location"]).data.decode()
    assert "Rejected" in page and "+1.5" in page


def test_bad_measurement_rerenders_form(client):
    response = record(client, "abc")
    assert response.status_code == 400
    assert b"is not a number" in response.data


def test_blank_measurement_rejected(client):
    response = record(client, "")
    assert response.status_code == 400
    assert b"no measurement for CH" in response.data


def test_spec_unavailable_records_nothing(client):
    assert record(client, "54", size="XXL").status_code == 400
    assert client.get("/samples/1").status_code == 404


def test_missing_round_is_404(client):
    assert client.get("/samples/999").status_code == 404
