import pytest

from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return create_app().test_client()


def make_jacket(client):
    response = client.post("/styles", data={
        "code": "JK-014", "name": "Wool blazer", "sizes": "XS, S, M, L, XL", "base_size": "M"})
    assert response.status_code == 302
    return response.headers["Location"]  # /styles/<id>


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_index_redirects_to_styles(client):
    assert client.get("/").headers["Location"] == "/styles"


def test_empty_list(client):
    assert b"No styles yet" in client.get("/styles").data


def test_create_style_and_list_it(client):
    make_jacket(client)
    assert b"JK-014" in client.get("/styles").data


def test_create_style_invalid_size_run(client):
    response = client.post("/styles", data={
        "code": "X", "name": "X", "sizes": "S, M", "base_size": "XL"})
    assert response.status_code == 400
    assert b"not in the size run" in response.data


def test_create_style_duplicate_code(client):
    make_jacket(client)
    response = client.post("/styles", data={
        "code": "JK-014", "name": "Again", "sizes": "M", "base_size": "M"})
    assert response.status_code == 400
    assert b"already used" in response.data


def test_add_pom_and_rules_show_graded_cm(client):
    url = make_jacket(client)
    client.post(f"{url}/poms", data={
        "code": "CH", "description": "Chest", "base_value_cm": "52", "tolerance_cm": "1"})
    page = client.get(url).data.decode()
    assert "52.0" in page and "—" in page  # base filled, other sizes missing rules

    pom_id = 1
    response = client.post(f"{url}/poms/{pom_id}/rules", data={
        "inc_S": "1.5", "inc_M": "2", "inc_L": "2", "inc_XL": "2.5"})
    assert response.status_code == 302
    page = client.get(url).data.decode()
    for cm in ("48.5", "50.0", "52.0", "54.0", "56.5"):
        assert cm in page


def test_add_pom_bad_cm(client):
    url = make_jacket(client)
    response = client.post(f"{url}/poms", data={
        "code": "CH", "description": "Chest", "base_value_cm": "52.25", "tolerance_cm": "1"})
    assert response.status_code == 400
    assert b"more precise than 1 mm" in response.data


def test_add_pom_zero_tolerance(client):
    url = make_jacket(client)
    response = client.post(f"{url}/poms", data={
        "code": "CH", "description": "Chest", "base_value_cm": "52", "tolerance_cm": "0"})
    assert response.status_code == 400


def test_bad_rule_saves_nothing(client):
    url = make_jacket(client)
    client.post(f"{url}/poms", data={
        "code": "CH", "description": "Chest", "base_value_cm": "52", "tolerance_cm": "1"})
    response = client.post(f"{url}/poms/1/rules", data={"inc_L": "2", "inc_XL": "abc"})
    assert response.status_code == 400
    assert "54.0" not in client.get(url).data.decode()  # L wasn't saved either


def test_rules_for_pom_of_other_style_is_404(client):
    url = make_jacket(client)
    client.post(f"{url}/poms", data={
        "code": "CH", "description": "Chest", "base_value_cm": "52", "tolerance_cm": "1"})
    other = client.post("/styles", data={
        "code": "SH-1", "name": "Shirt", "sizes": "S, M", "base_size": "M"}).headers["Location"]
    assert client.post(f"{other}/poms/1/rules", data={"inc_M": "2"}).status_code == 404


def test_missing_style_is_404(client):
    assert client.get("/styles/999").status_code == 404
    assert client.post("/styles/999/poms", data={}).status_code == 404
    assert client.post("/styles/999/delete").status_code == 404


def test_delete_style(client):
    url = make_jacket(client)
    assert client.post(f"{url}/delete").headers["Location"] == "/styles"
    assert client.get(url).status_code == 404