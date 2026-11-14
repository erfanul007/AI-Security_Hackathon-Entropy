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


PATIENT = dict(mrn="DEMO000001", first_name="Ann", last_name="Lee", date_of_birth="1980-01-02", sex_at_birth="F",
               interpreter_needed=False, registration_date="2024-01-01", confidentiality_level="standard",
               portal_active=True, advance_directive_on_file=False)


def post(client, t, body, status=201):
    r = client.post(f"/api/tables/{t}", json=body)
    assert r.status_code == status, r.text
    return r.json()


def org(client):
    """facility, department, employee (Doe, Jane), provider (MD); returns their ids."""
    f = post(client, "facilities", dict(facility_code="F1", name="Main", facility_type="Urgent Care", npi="9990000001",
                                        tax_id="99-0000001", address_line1="1 Main St", city="Portsmouth", state="OH", zip="45662"))
    d = post(client, "departments", dict(facility_id=f["facility_id"], department_name="UC", specialty="UC", cost_center="C1"))
    e = post(client, "employees", dict(employee_number="DEMO1", first_name="Jane", last_name="Doe", date_of_birth="1970-01-01",
                                       sex="F", ssn="900-00-0001", job_title="Physician", job_code="MD", hire_date="2020-01-01",
                                       employment_status="Active", fte=1, pay_type="Salary", work_email="j@example.org"))
    p = post(client, "providers", dict(employee_id=e["employee_id"], npi="9990000002", credential="MD",
                                       specialty="Family Medicine", taxonomy_code="207Q00000X", board_certified=True,
                                       accepting_new_patients=True))
    return f["facility_id"], d["department_id"], e["employee_id"], p["provider_id"]


def encounter(client, pid, f, d, **over):
    return post(client, "encounters", dict(csn="DEMO-1", patient_id=pid, facility_id=f, department_id=d,
                                           encounter_type="Urgent Care", encounter_class="AMB",
                                           start_datetime="2026-01-01T09:00", status="Completed") | over)


def test_patient_crud_roundtrip(client):
    p = post(client, "patients", PATIENT)
    pid = p["patient_id"]
    assert client.get(f"/api/tables/patients/{pid}").json()["first_name"] == "Ann"
    assert client.put(f"/api/tables/patients/{pid}", json={"first_name": "Bea"}).status_code == 200
    assert client.get(f"/api/tables/patients/{pid}").json()["first_name"] == "Bea"
    assert client.delete(f"/api/tables/patients/{pid}").status_code == 200
    assert client.get(f"/api/tables/patients/{pid}").status_code == 404


def test_strict_rejected(client):
    r = client.post("/api/tables/patients", json=PATIENT | {"sex_at_birth": "X"})
    assert r.status_code == 400 and "sex_at_birth" in r.json()["detail"]


def test_required_and_empty_string(client):
    assert client.post("/api/tables/patients", json={k: v for k, v in PATIENT.items() if k != "mrn"}).status_code == 400
    assert client.post("/api/tables/patients", json=PATIENT | {"mrn": ""}).status_code == 400
    p = post(client, "patients", PATIENT | {"middle_name": ""})
    assert p["middle_name"] is None


def test_type_shape(client):
    p = post(client, "patients", PATIENT | {"interpreter_needed": True})
    assert p["interpreter_needed"] == 1
    assert client.post("/api/tables/patients", json=PATIENT | {"household_id": "abc"}).status_code == 400
    assert client.post("/api/tables/patients", json=PATIENT | {"date_of_birth": "2024-13-40"}).status_code == 400


def test_date_pair(client):
    f, d, _, _ = org(client)
    pid = post(client, "patients", PATIENT)["patient_id"]
    r = client.post("/api/tables/encounters", json=dict(csn="DEMO-1", patient_id=pid, facility_id=f, department_id=d,
                                                        encounter_type="Urgent Care", encounter_class="AMB", status="Completed",
                                                        start_datetime="2026-01-02T09:00", end_datetime="2026-01-01T09:00"))
    assert r.status_code == 400


def test_whitelist(client):
    assert client.get("/api/tables/nope").status_code == 404
    assert client.get("/api/tables/patients?sort=evil").status_code == 400
    assert client.post("/api/tables/patients", json=PATIENT | {"evil": 1}).status_code == 400


def test_search_quotes(client):
    post(client, "patients", PATIENT)
    r = client.get("/api/tables/patients", params={"q": "'%_"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/api/tables/patients", params={"q": "lee"}).json()["total"] == 1


def test_put_pk(client):
    post(client, "chargemaster", dict(charge_code="C1", description="Visit", revenue_code="0510", standard_charge=100))
    assert client.put("/api/tables/chargemaster/C1", json={"charge_code": "C2"}).status_code == 400
    assert client.put("/api/tables/chargemaster/C1", json={"charge_code": "C1", "standard_charge": 120}).status_code == 200


def test_fk_label_and_options(client):
    org(client)
    rows = client.get("/api/tables/providers").json()["rows"]
    assert "Doe, Jane" in rows[0]["employee_id_label"]
    opts = client.get("/api/options/providers", params={"q": "Doe"}).json()
    assert opts == [{"id": rows[0]["provider_id"], "label": "Doe, Jane · MD"}]
