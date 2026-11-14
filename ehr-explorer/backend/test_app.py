import pytest
from fastapi.testclient import TestClient

import app
import rules


@pytest.fixture
def client(tmp_path):
    app.DB_PATH = tmp_path / "t.db"
    app.init_db()
    return TestClient(app.app)


def test_schema_has_30_tables(client):
    assert len(app.META) == 30


def test_meta_shape(client):
    m = client.get("/api/meta").json()
    t = m["tables"]
    emp = next(c for c in t["providers"]["columns"] if c["name"] == "employee_id")
    assert emp["fk"] == "employees" and emp["required"]
    sex = next(c for c in t["patients"]["columns"] if c["name"] == "sex_at_birth")
    assert sex["strict"] == ["F", "M"]
    assert t["social_history"]["pk"] == "patient_id"
    assert t["chargemaster"]["pk"] == "charge_code"
    assert all(v["group"] in rules.GROUPS for v in t.values())
    assert list(m["groups"]) == ["Clinical", "Organization", "Billing", "Admin & Security"]


def test_env(client, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert client.get("/api/env").json() == {"env": "demo"}


def test_init_idempotent(client):
    app.init_db()
    app.init_db()
