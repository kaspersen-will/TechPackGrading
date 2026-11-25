"""The system description must match the code (assignment §8a).

- openapi.yaml is a valid OpenAPI 3 document;
- it lists exactly the routes and methods Flask serves, no more, no fewer;
- system.yaml lists exactly the environment variables this service's code
  reads, with the same defaults.
No database needed: create_app() only reads DATABASE_URL, it doesn't connect.
"""

import re
from pathlib import Path

import pytest
import yaml
from openapi_spec_validator import validate

from app import create_app

SERVICE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_DIR.parent.parent
SERVICE = SERVICE_DIR.name
IGNORED_METHODS = {"HEAD", "OPTIONS"}  # added by Flask itself


def load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def openapi():
    return load_yaml(SERVICE_DIR / "openapi.yaml")


def served_routes(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@127.0.0.1:1/nothing_test")
    app = create_app()
    routes = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        # Flask's /styles/<int:style_id> is OpenAPI's /styles/{style_id}
        path = re.sub(r"<(?:[a-z]+:)?([a-z_]+)>", r"{\1}", rule.rule)
        routes |= {(method, path) for method in rule.methods - IGNORED_METHODS}
    return routes


def test_openapi_document_is_valid(openapi):
    validate(openapi)


def test_openapi_lists_exactly_the_served_routes(openapi, monkeypatch):
    documented = {
        (method.upper(), path)
        for path, item in openapi["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    served = served_routes(monkeypatch)
    assert served - documented == set(), "served but missing from openapi.yaml"
    assert documented - served == set(), "in openapi.yaml but not served"


def env_reads_in_code():
    """NAME -> default (None if read without one) for every os.environ read outside tests/."""
    found = {}
    pattern = re.compile(
        r'os\.environ(?:\.get\(\s*"([A-Z0-9_]+)"(?:\s*,\s*"([^"]*)")?'  # .get("NAME", "default")
        r'|\[\s*"([A-Z0-9_]+)"\s*\])'                                 # ["NAME"]
    )
    for path in SERVICE_DIR.rglob("*.py"):
        if "tests" in path.relative_to(SERVICE_DIR).parts:
            continue
        for get_name, default, index_name in pattern.findall(path.read_text(encoding="utf-8")):
            name = get_name or index_name
            if default or name not in found:
                found[name] = default or found.get(name)
    return found


def test_system_yaml_lists_every_env_var_with_its_code_default():
    env = load_yaml(REPO_ROOT / "system.yaml")["services"][SERVICE]["env"]
    in_code = env_reads_in_code()
    assert set(env) == set(in_code)
    for name, default in in_code.items():
        if env[name].get("secret"):
            assert default is None, f"{name} is a secret but the code has a default"
        else:
            assert str(env[name]["default"]) == default, name
