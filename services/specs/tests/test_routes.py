"""The JSON API against a real SQL Server test database (skipped without TEST_DATABASE_URL)."""

import pytest

from app import create_app


@pytest.fixture
def client(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    return create_app().test_client()


JACKET = {"code": "JK-014", "name": "Wool blazer", "sizes": ["XS", "S", "M", "L", "XL"],
          "base_size": "M"}
CHEST = {"code": "CH", "description": "Chest", "base_value_mm": 520, "tolerance_mm": 10}


def make_jacket(client):
    response = client.post("/styles", json=JACKET)
    assert response.status_code == 201
    return f"/styles/{response.get_json()['id']}"


def add_chest(client, url):
    response = client.post(f"{url}/poms", json=CHEST)
    assert response.status_code == 201
    return response.get_json()["id"]


def test_health_writes_to_own_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_empty_list(client):
    assert client.get("/styles").get_json() == []


def test_create_style_and_list_it(client):
    url = make_jacket(client)
    [style] = client.get("/styles").get_json()
    assert style["code"] == "JK-014" and url == f"/styles/{style['id']}"


def test_create_style_invalid_size_run(client):
    response = client.post("/styles", json={**JACKET, "base_size": "XXL"})
    assert response.status_code == 400
    assert "not in the size run" in response.get_json()["error"]


def test_create_style_needs_a_json_body(client):
    assert client.post("/styles", data="code=JK").status_code == 400
    assert client.post("/styles", json={**JACKET, "sizes": "XS, S"}).status_code == 400
    assert client.post("/styles", json={**JACKET, "code": "  "}).status_code == 400


def test_create_style_duplicate_code_is_409(client):
    make_jacket(client)
    response = client.post("/styles", json=JACKET)
    assert response.status_code == 409
    assert "already used" in response.get_json()["error"]


def test_style_shows_size_run_per_pom(client):
    url = make_jacket(client)
    add_chest(client, url)
    body = client.get(url).get_json()
    assert body["sizes"] == ["XS", "S", "M", "L", "XL"]
    [pom] = body["poms"]
    assert pom["rules"] == {}
    assert pom["size_run"] == {"XS": None, "S": None, "M": 520, "L": None, "XL": None}


def test_rules_grade_the_whole_run(client):
    url = make_jacket(client)
    pom_id = add_chest(client, url)
    response = client.put(f"{url}/poms/{pom_id}/rules",
                          json={"increments_mm": {"S": 15, "M": 20, "L": 20, "XL": 25}})
    assert response.status_code == 204
    [pom] = client.get(url).get_json()["poms"]
    assert pom["size_run"] == {"XS": 485, "S": 500, "M": 520, "L": 540, "XL": 565}


def test_add_pom_fractional_mm_is_400(client):
    url = make_jacket(client)
    response = client.post(f"{url}/poms", json={**CHEST, "base_value_mm": 522.5})
    assert response.status_code == 400
    assert "whole number of mm" in response.get_json()["error"]


def test_add_pom_zero_tolerance_is_400(client):
    url = make_jacket(client)
    assert client.post(f"{url}/poms", json={**CHEST, "tolerance_mm": 0}).status_code == 400


def test_add_pom_duplicate_code_is_409(client):
    url = make_jacket(client)
    add_chest(client, url)
    assert client.post(f"{url}/poms", json=CHEST).status_code == 409


def test_bad_rule_saves_nothing(client):
    url = make_jacket(client)
    pom_id = add_chest(client, url)
    response = client.put(f"{url}/poms/{pom_id}/rules",
                          json={"increments_mm": {"L": 20, "XL": "abc"}})
    assert response.status_code == 400
    [pom] = client.get(url).get_json()["poms"]
    assert pom["rules"] == {}  # L wasn't saved either


def test_rule_for_smallest_size_is_400(client):
    url = make_jacket(client)
    pom_id = add_chest(client, url)
    response = client.put(f"{url}/poms/{pom_id}/rules", json={"increments_mm": {"XS": 10}})
    assert response.status_code == 400


def test_rules_for_pom_of_other_style_is_404(client):
    url = make_jacket(client)
    pom_id = add_chest(client, url)
    other = client.post("/styles", json={"code": "SH-1", "name": "Shirt", "sizes": ["S", "M"],
                                         "base_size": "M"}).get_json()["id"]
    response = client.put(f"/styles/{other}/poms/{pom_id}/rules", json={"increments_mm": {"M": 2}})
    assert response.status_code == 404


def test_graded_spec_is_what_samples_receives(client):
    url = make_jacket(client)
    pom_id = add_chest(client, url)
    client.put(f"{url}/poms/{pom_id}/rules", json={"increments_mm": {"L": 20}})
    assert client.get(f"{url}/spec/L").get_json() == {
        "style_code": "JK-014",
        "poms": [{"pom_id": pom_id, "code": "CH", "description": "Chest",
                  "target_mm": 540, "tolerance_mm": 10}],
    }


def test_graded_spec_unknown_size_is_404_missing_rule_is_422(client):
    url = make_jacket(client)
    add_chest(client, url)
    assert client.get(f"{url}/spec/XXL").status_code == 404
    assert client.get("/styles/999/spec/M").status_code == 404
    response = client.get(f"{url}/spec/XL")
    assert response.status_code == 422
    assert "missing grade rule" in response.get_json()["error"]


def test_missing_style_is_404(client):
    assert client.get("/styles/999").status_code == 404
    assert client.post("/styles/999/poms", json=CHEST).status_code == 404
    assert client.delete("/styles/999").status_code == 404


def test_delete_style(client):
    url = make_jacket(client)
    add_chest(client, url)
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
