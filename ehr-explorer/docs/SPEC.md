# EHR Explorer — Spec

A small local app to store and browse data shaped like the Scioto Ridge Health EHR database.
SQLite + FastAPI backend, React frontend. No auth.

Status: re-derived against the **real** database, 2026-11-14. Not implemented yet.

## 0. Provenance & correction

The schema below was read **directly from the live database** via Riley's `query_db` tool, using
`sqlite_master`, the `pragma_table_info()` / `pragma_foreign_key_list()` table-valued functions, and
`SELECT DISTINCT` / `COUNT` probes — metadata and aggregates only, no patient rows pulled. It supersedes
an earlier draft of this spec that was built from Riley *describing* the DB in prose. That draft was
wrong: Riley invented 5 tables that don't exist (`staff`, `schedules`, `service_codes`, `tasks`,
`user_roles`), omitted ~13 real ones, and misreported columns. A supplied ER diagram was also wrong
(it showed provider names and `patient_contacts.email/address`, none of which exist). Trust only what was
probed from `sqlite_master` / `pragma_*`.

The real DB has **30 tables** (§4). Approx live row counts seen while probing: access_audit_log ~103.9k,
claim_lines ~27.8k, clinical_notes ~12.6k, encounters ~12.5k, claims ~11.4k, medications ~3.3k,
patient_contacts 544, patient_coverage 458, patients 450, employees 178, app_users 182, providers 55.
Our app ships its **own synthetic data**; those counts are only to show the real DB's shape.

## 1. Goals / non-goals

**Goals**
- Exact copy of the real 30-table schema (§4) in SQLite, column names/types/constraints/FKs verbatim.
- Create / read / update / delete any row in any table through a generic, schema-driven UI.
- Dashboard with charts (§8) and a patient detail page.
- Two databases, `demo` (seeded synthetic data) and `prod` (empty), switched by env var.

**Non-goals (v1)**
- Auth / permissions. The `app_users` / `roles` / `role_permissions` tables are just data.
- CSV import/export, bulk edit, date-range filters.
- Detail pages other than patient.
- Any real PHI. Sensitive columns exist in the schema and are kept (see §1a), but only synthetic
  placeholder values are ever stored.

### 1a. Sensitive columns (decision: include, show raw)

The real schema contains: `patients.ssn`, `employees.ssn` / `bank_routing_number` / `bank_account_last4`,
`patient_payments.card_last4` / `card_exp` / `processor_token`, `providers.dea_number` /
`state_license_number`, `employees.hourly_rate` / `annual_salary`, and the full `social_history` table
(substance use, sexual orientation, etc.). These are **kept and shown/edited like any other field** — the
app is local and all data is synthetic. The seed (§9) fills them with obvious fakes only
(SSN `900-xx-xxxx`, card last4 `0000`, routing `000000000`, DEA `X9999999`).

## 2. Stack & layout

| Part | Choice |
|---|---|
| Backend | Python, FastAPI + uvicorn, stdlib `sqlite3`, raw SQL, no ORM |
| Frontend | Vite + React + TypeScript, Recharts, plain CSS, no router lib (state-based nav), no UI kit |
| Tests | One pytest file for the backend |

```
ehr-explorer/
  docs/SPEC.md
  backend/
    app.py            # FastAPI app, all routes
    schema.sql        # exact DDL (§4), CREATE TABLE IF NOT EXISTS
    seed.py           # demo-only synthetic data
    test_app.py
    requirements.txt  # fastapi, uvicorn, pytest, httpx
  frontend/           # Vite project; dev proxies /api -> :8000
  data/               # demo.db, prod.db (gitignored)
```

**Run modes**
- Dev: `uvicorn app:app --reload` (port 8000) + `npm run dev` (Vite, proxies `/api`).
- Single process: `npm run build`, then FastAPI serves `frontend/dist` at `/`.

## 3. Environments

- `APP_ENV=demo|prod`, default `demo`.
- `demo` -> `ehr-explorer/data/demo.db`, `prod` -> `ehr-explorer/data/prod.db`.
- On startup the backend runs `schema.sql` (idempotent), so a missing DB is created empty.
- Every connection runs `PRAGMA foreign_keys=ON`.
- `seed.py` drops and recreates `demo.db` with a fixed random seed. It **refuses** (exit non-zero) if
  `APP_ENV=prod` or the target path is `prod.db`.
- UI header shows a `DEMO` / `PROD` badge (from `GET /api/env`).
- `data/*.db` is gitignored.

## 4. Schema (exact copy of the real DB)

30 tables, grouped for the sidebar. `req` = NOT NULL. `key` = PK or the FK target table. `VARCHAR(n)`
lengths are copied into the DDL but **not validated** (SQLite ignores them). Types kept verbatim:
`NUMERIC(p,s)` money as decimal, `DATE` = `YYYY-MM-DD`, `TIMESTAMP` = ISO-8601, `BOOLEAN` = 0/1.
`social_history` has `patient_id` as its own primary key (one row per patient).

### Clinical

#### `patients`

| column | type | req | key |
|---|---|---|---|
| patient_id | INTEGER |  | PK |
| mrn | VARCHAR(12) | ✓ |  |
| first_name | VARCHAR(60) | ✓ |  |
| middle_name | VARCHAR(60) |  |  |
| last_name | VARCHAR(60) | ✓ |  |
| suffix | VARCHAR(10) |  |  |
| preferred_name | VARCHAR(60) |  |  |
| date_of_birth | DATE | ✓ |  |
| sex_at_birth | CHAR(1) | ✓ |  |
| gender_identity | VARCHAR(40) |  |  |
| race | VARCHAR(60) |  |  |
| ethnicity | VARCHAR(40) |  |  |
| preferred_language | VARCHAR(30) |  |  |
| interpreter_needed | BOOLEAN | ✓ |  |
| marital_status | VARCHAR(20) |  |  |
| ssn | CHAR(11) |  |  |
| address_line1 | VARCHAR(120) |  |  |
| address_line2 | VARCHAR(60) |  |  |
| city | VARCHAR(60) |  |  |
| state | CHAR(2) |  |  |
| zip | VARCHAR(10) |  |  |
| county | VARCHAR(40) |  |  |
| home_phone | VARCHAR(20) |  |  |
| mobile_phone | VARCHAR(20) |  |  |
| email | VARCHAR(120) |  |  |
| household_id | INTEGER |  |  |
| pcp_provider_id | INTEGER |  | FK → providers |
| employee_id | INTEGER |  | FK → employees |
| registration_date | DATE | ✓ |  |
| deceased_date | DATE |  |  |
| confidentiality_level | VARCHAR(20) | ✓ |  |
| confidentiality_note | VARCHAR(255) |  |  |
| portal_active | BOOLEAN | ✓ |  |
| advance_directive_on_file | BOOLEAN | ✓ |  |

#### `encounters`

| column | type | req | key |
|---|---|---|---|
| encounter_id | INTEGER |  | PK |
| csn | VARCHAR(12) | ✓ |  |
| patient_id | INTEGER | ✓ | FK → patients |
| facility_id | INTEGER | ✓ | FK → facilities |
| department_id | INTEGER | ✓ | FK → departments |
| attending_provider_id | INTEGER |  | FK → providers |
| encounter_type | VARCHAR(40) | ✓ |  |
| encounter_class | VARCHAR(10) | ✓ |  |
| admit_source | VARCHAR(40) |  |  |
| start_datetime | TIMESTAMP | ✓ |  |
| end_datetime | TIMESTAMP |  |  |
| chief_complaint | VARCHAR(255) |  |  |
| discharge_disposition | VARCHAR(60) |  |  |
| primary_coverage_id | INTEGER |  | FK → patient_coverage |
| status | VARCHAR(20) | ✓ |  |

#### `encounter_diagnoses`

| column | type | req | key |
|---|---|---|---|
| encounter_diagnosis_id | INTEGER |  | PK |
| encounter_id | INTEGER | ✓ | FK → encounters |
| sequence_number | INTEGER | ✓ |  |
| icd10_code | VARCHAR(10) | ✓ |  |
| description | VARCHAR(255) | ✓ |  |
| is_primary | BOOLEAN | ✓ |  |
| present_on_admission | CHAR(1) |  |  |

#### `clinical_notes`

| column | type | req | key |
|---|---|---|---|
| note_id | INTEGER |  | PK |
| encounter_id | INTEGER | ✓ | FK → encounters |
| patient_id | INTEGER | ✓ | FK → patients |
| author_provider_id | INTEGER |  | FK → providers |
| note_type | VARCHAR(40) | ✓ |  |
| note_datetime | TIMESTAMP | ✓ |  |
| note_text | TEXT | ✓ |  |
| is_sensitive | BOOLEAN | ✓ |  |
| sensitivity_reason | VARCHAR(80) |  |  |
| signed | BOOLEAN | ✓ |  |

#### `allergies`

| column | type | req | key |
|---|---|---|---|
| allergy_id | INTEGER |  | PK |
| patient_id | INTEGER | ✓ | FK → patients |
| allergen | VARCHAR(80) | ✓ |  |
| allergen_type | VARCHAR(20) | ✓ |  |
| reaction | VARCHAR(80) |  |  |
| severity | VARCHAR(20) |  |  |
| status | VARCHAR(20) | ✓ |  |
| recorded_date | DATE | ✓ |  |

#### `problem_list`

| column | type | req | key |
|---|---|---|---|
| problem_id | INTEGER |  | PK |
| patient_id | INTEGER | ✓ | FK → patients |
| icd10_code | VARCHAR(10) | ✓ |  |
| description | VARCHAR(255) | ✓ |  |
| onset_date | DATE |  |  |
| noted_date | DATE | ✓ |  |
| resolved_date | DATE |  |  |
| status | VARCHAR(20) | ✓ |  |
| noted_by_provider_id | INTEGER |  | FK → providers |

#### `medications`

| column | type | req | key |
|---|---|---|---|
| medication_order_id | INTEGER |  | PK |
| patient_id | INTEGER | ✓ | FK → patients |
| encounter_id | INTEGER |  | FK → encounters |
| prescriber_provider_id | INTEGER |  | FK → providers |
| rxnorm_ingredient_rxcui | INTEGER |  |  |
| medication_name | VARCHAR(160) | ✓ |  |
| dose | VARCHAR(40) |  |  |
| route | VARCHAR(30) |  |  |
| frequency | VARCHAR(40) |  |  |
| sig | VARCHAR(255) |  |  |
| quantity | INTEGER |  |  |
| refills | INTEGER |  |  |
| start_date | DATE | ✓ |  |
| end_date | DATE |  |  |
| status | VARCHAR(20) | ✓ |  |
| indication_icd10 | VARCHAR(10) |  |  |
| pharmacy | VARCHAR(80) |  |  |
| is_controlled_substance | BOOLEAN | ✓ |  |

#### `immunizations`

| column | type | req | key |
|---|---|---|---|
| immunization_id | INTEGER |  | PK |
| patient_id | INTEGER | ✓ | FK → patients |
| encounter_id | INTEGER |  | FK → encounters |
| cvx_code | VARCHAR(4) | ✓ |  |
| vaccine_name | VARCHAR(160) | ✓ |  |
| administered_date | DATE | ✓ |  |
| lot_number | VARCHAR(20) |  |  |
| manufacturer | VARCHAR(60) |  |  |
| site | VARCHAR(30) |  |  |
| route | VARCHAR(20) |  |  |
| administered_by_employee_id | INTEGER |  | FK → employees |

#### `procedures`

| column | type | req | key |
|---|---|---|---|
| procedure_id | INTEGER |  | PK |
| encounter_id | INTEGER | ✓ | FK → encounters |
| patient_id | INTEGER | ✓ | FK → patients |
| code | VARCHAR(10) | ✓ |  |
| code_system | VARCHAR(10) | ✓ |  |
| description | VARCHAR(255) | ✓ |  |
| modifier | VARCHAR(10) |  |  |
| units | INTEGER | ✓ |  |
| performed_datetime | TIMESTAMP | ✓ |  |
| performing_provider_id | INTEGER |  | FK → providers |

#### `vitals`

| column | type | req | key |
|---|---|---|---|
| vital_id | INTEGER |  | PK |
| encounter_id | INTEGER | ✓ | FK → encounters |
| patient_id | INTEGER | ✓ | FK → patients |
| recorded_datetime | TIMESTAMP | ✓ |  |
| systolic_bp | INTEGER |  |  |
| diastolic_bp | INTEGER |  |  |
| heart_rate | INTEGER |  |  |
| respiratory_rate | INTEGER |  |  |
| temperature_f | NUMERIC(4,1) |  |  |
| spo2_pct | INTEGER |  |  |
| height_cm | NUMERIC(5,1) |  |  |
| weight_kg | NUMERIC(5,1) |  |  |
| bmi | NUMERIC(4,1) |  |  |
| pain_score | INTEGER |  |  |
| recorded_by_employee_id | INTEGER |  | FK → employees |

#### `screenings`

| column | type | req | key |
|---|---|---|---|
| screening_id | INTEGER |  | PK |
| encounter_id | INTEGER | ✓ | FK → encounters |
| patient_id | INTEGER | ✓ | FK → patients |
| instrument | VARCHAR(30) | ✓ |  |
| loinc_code | VARCHAR(10) |  |  |
| score | INTEGER | ✓ |  |
| interpretation | VARCHAR(60) |  |  |
| administered_datetime | TIMESTAMP | ✓ |  |

#### `social_history`

| column | type | req | key |
|---|---|---|---|
| patient_id | INTEGER |  | PK |
| tobacco_status | VARCHAR(30) |  |  |
| tobacco_packs_per_day | NUMERIC(3,1) |  |  |
| tobacco_start_year | INTEGER |  |  |
| tobacco_quit_year | INTEGER |  |  |
| alcohol_use | VARCHAR(20) |  |  |
| alcohol_drinks_per_week | INTEGER |  |  |
| drug_use | VARCHAR(20) |  |  |
| drug_types | VARCHAR(120) |  |  |
| sexually_active | VARCHAR(20) |  |  |
| sexual_orientation | VARCHAR(40) |  |  |
| occupation | VARCHAR(80) |  |  |
| employer | VARCHAR(80) |  |  |
| education_level | VARCHAR(60) |  |  |
| living_situation | VARCHAR(60) |  |  |
| food_insecurity | BOOLEAN |  |  |
| housing_insecurity | BOOLEAN |  |  |
| last_reviewed_date | DATE |  |  |

#### `lab_orders`

| column | type | req | key |
|---|---|---|---|
| lab_order_id | INTEGER |  | PK |
| accession_number | VARCHAR(16) | ✓ |  |
| encounter_id | INTEGER | ✓ | FK → encounters |
| patient_id | INTEGER | ✓ | FK → patients |
| ordering_provider_id | INTEGER |  | FK → providers |
| panel_name | VARCHAR(80) | ✓ |  |
| cpt_code | VARCHAR(10) |  |  |
| order_datetime | TIMESTAMP | ✓ |  |
| collected_datetime | TIMESTAMP |  |  |
| resulted_datetime | TIMESTAMP |  |  |
| status | VARCHAR(20) | ✓ |  |

#### `lab_results`

| column | type | req | key |
|---|---|---|---|
| lab_result_id | INTEGER |  | PK |
| lab_order_id | INTEGER | ✓ | FK → lab_orders |
| patient_id | INTEGER | ✓ | FK → patients |
| loinc_code | VARCHAR(10) | ✓ |  |
| test_name | VARCHAR(255) | ✓ |  |
| value_numeric | NUMERIC(12,3) |  |  |
| value_text | VARCHAR(120) |  |  |
| unit | VARCHAR(20) |  |  |
| reference_range | VARCHAR(40) |  |  |
| abnormal_flag | VARCHAR(4) |  |  |
| resulted_datetime | TIMESTAMP | ✓ |  |

#### `patient_contacts`

| column | type | req | key |
|---|---|---|---|
| contact_id | INTEGER |  | PK |
| patient_id | INTEGER | ✓ | FK → patients |
| related_patient_id | INTEGER |  | FK → patients |
| first_name | VARCHAR(60) | ✓ |  |
| last_name | VARCHAR(60) | ✓ |  |
| relationship | VARCHAR(30) | ✓ |  |
| phone | VARCHAR(20) |  |  |
| is_emergency_contact | BOOLEAN | ✓ |  |
| is_legal_guardian | BOOLEAN | ✓ |  |
| is_healthcare_poa | BOOLEAN | ✓ |  |

### Organization

#### `facilities`

| column | type | req | key |
|---|---|---|---|
| facility_id | INTEGER |  | PK |
| facility_code | VARCHAR(12) | ✓ |  |
| name | VARCHAR(120) | ✓ |  |
| facility_type | VARCHAR(40) | ✓ |  |
| npi | CHAR(10) | ✓ |  |
| tax_id | VARCHAR(12) | ✓ |  |
| address_line1 | VARCHAR(120) | ✓ |  |
| city | VARCHAR(60) | ✓ |  |
| state | CHAR(2) | ✓ |  |
| zip | VARCHAR(10) | ✓ |  |
| county | VARCHAR(40) |  |  |
| main_phone | VARCHAR(20) |  |  |
| licensed_beds | INTEGER |  |  |
| opened_date | DATE |  |  |

#### `departments`

| column | type | req | key |
|---|---|---|---|
| department_id | INTEGER |  | PK |
| facility_id | INTEGER | ✓ | FK → facilities |
| department_name | VARCHAR(120) | ✓ |  |
| specialty | VARCHAR(20) | ✓ |  |
| cost_center | VARCHAR(10) | ✓ |  |
| phone | VARCHAR(20) |  |  |

#### `providers`

| column | type | req | key |
|---|---|---|---|
| provider_id | INTEGER |  | PK |
| employee_id | INTEGER | ✓ | FK → employees |
| npi | CHAR(10) | ✓ |  |
| dea_number | CHAR(9) |  |  |
| state_license_number | VARCHAR(20) |  |  |
| license_state | CHAR(2) |  |  |
| license_expiration | DATE |  |  |
| credential | VARCHAR(20) | ✓ |  |
| specialty | VARCHAR(80) | ✓ |  |
| taxonomy_code | VARCHAR(12) | ✓ |  |
| primary_department_id | INTEGER |  | FK → departments |
| board_certified | BOOLEAN | ✓ |  |
| accepting_new_patients | BOOLEAN | ✓ |  |

#### `employees`

| column | type | req | key |
|---|---|---|---|
| employee_id | INTEGER |  | PK |
| employee_number | VARCHAR(10) | ✓ |  |
| first_name | VARCHAR(60) | ✓ |  |
| middle_name | VARCHAR(60) |  |  |
| last_name | VARCHAR(60) | ✓ |  |
| date_of_birth | DATE | ✓ |  |
| sex | CHAR(1) | ✓ |  |
| ssn | CHAR(11) | ✓ |  |
| job_title | VARCHAR(80) | ✓ |  |
| job_code | VARCHAR(10) | ✓ |  |
| department_id | INTEGER |  | FK → departments |
| facility_id | INTEGER |  | FK → facilities |
| manager_employee_id | INTEGER |  | FK → employees |
| hire_date | DATE | ✓ |  |
| termination_date | DATE |  |  |
| employment_status | VARCHAR(20) | ✓ |  |
| fte | NUMERIC(3,2) | ✓ |  |
| pay_type | VARCHAR(10) | ✓ |  |
| hourly_rate | NUMERIC(8,2) |  |  |
| annual_salary | NUMERIC(12,2) |  |  |
| work_email | VARCHAR(120) | ✓ |  |
| work_phone | VARCHAR(20) |  |  |
| personal_phone | VARCHAR(20) |  |  |
| home_address_line1 | VARCHAR(120) |  |  |
| home_city | VARCHAR(60) |  |  |
| home_state | CHAR(2) |  |  |
| home_zip | VARCHAR(10) |  |  |
| bank_routing_number | CHAR(9) |  |  |
| bank_account_last4 | CHAR(4) |  |  |
| emergency_contact_name | VARCHAR(120) |  |  |
| emergency_contact_phone | VARCHAR(20) |  |  |

### Billing

#### `payers`

| column | type | req | key |
|---|---|---|---|
| payer_id | INTEGER |  | PK |
| payer_name | VARCHAR(120) | ✓ |  |
| payer_type | VARCHAR(30) | ✓ |  |
| edi_payer_id | VARCHAR(10) | ✓ |  |
| claims_phone | VARCHAR(20) |  |  |

#### `insurance_plans`

| column | type | req | key |
|---|---|---|---|
| plan_id | INTEGER |  | PK |
| payer_id | INTEGER | ✓ | FK → payers |
| plan_name | VARCHAR(120) | ✓ |  |
| plan_type | VARCHAR(40) | ✓ |  |
| deductible_individual | NUMERIC(10,2) |  |  |
| oop_max_individual | NUMERIC(10,2) |  |  |
| coinsurance_pct | INTEGER |  |  |
| copay_pcp | NUMERIC(8,2) |  |  |
| copay_specialist | NUMERIC(8,2) |  |  |
| copay_er | NUMERIC(8,2) |  |  |

#### `patient_coverage`

| column | type | req | key |
|---|---|---|---|
| coverage_id | INTEGER |  | PK |
| patient_id | INTEGER | ✓ | FK → patients |
| plan_id | INTEGER | ✓ | FK → insurance_plans |
| coverage_priority | INTEGER | ✓ |  |
| member_id | VARCHAR(20) | ✓ |  |
| group_number | VARCHAR(20) |  |  |
| subscriber_first_name | VARCHAR(60) |  |  |
| subscriber_last_name | VARCHAR(60) |  |  |
| subscriber_dob | DATE |  |  |
| relationship_to_subscriber | VARCHAR(20) | ✓ |  |
| effective_date | DATE | ✓ |  |
| termination_date | DATE |  |  |

#### `claims`

| column | type | req | key |
|---|---|---|---|
| claim_id | INTEGER |  | PK |
| claim_number | VARCHAR(20) | ✓ |  |
| encounter_id | INTEGER | ✓ | FK → encounters |
| patient_id | INTEGER | ✓ | FK → patients |
| coverage_id | INTEGER |  | FK → patient_coverage |
| payer_id | INTEGER |  | FK → payers |
| claim_type | VARCHAR(10) | ✓ |  |
| billing_npi | CHAR(10) | ✓ |  |
| rendering_provider_id | INTEGER |  | FK → providers |
| drg_code | VARCHAR(4) |  |  |
| drg_description | VARCHAR(160) |  |  |
| service_date_from | DATE | ✓ |  |
| service_date_to | DATE | ✓ |  |
| submitted_date | DATE |  |  |
| adjudicated_date | DATE |  |  |
| total_charge | NUMERIC(12,2) | ✓ |  |
| allowed_amount | NUMERIC(12,2) |  |  |
| paid_amount | NUMERIC(12,2) |  |  |
| contractual_adjustment | NUMERIC(12,2) |  |  |
| patient_responsibility | NUMERIC(12,2) |  |  |
| status | VARCHAR(20) | ✓ |  |
| denial_code | VARCHAR(10) |  |  |
| denial_reason | VARCHAR(255) |  |  |

#### `claim_lines`

| column | type | req | key |
|---|---|---|---|
| claim_line_id | INTEGER |  | PK |
| claim_id | INTEGER | ✓ | FK → claims |
| line_number | INTEGER | ✓ |  |
| charge_code | VARCHAR(10) | ✓ | FK → chargemaster |
| revenue_code | CHAR(4) |  |  |
| modifier | VARCHAR(10) |  |  |
| icd10_pointer | VARCHAR(10) |  |  |
| units | INTEGER | ✓ |  |
| charge_amount | NUMERIC(12,2) | ✓ |  |
| allowed_amount | NUMERIC(12,2) |  |  |
| paid_amount | NUMERIC(12,2) |  |  |

#### `chargemaster`

| column | type | req | key |
|---|---|---|---|
| charge_code | VARCHAR(10) |  | PK |
| description | VARCHAR(160) | ✓ |  |
| revenue_code | CHAR(4) | ✓ |  |
| standard_charge | NUMERIC(10,2) | ✓ |  |

#### `patient_payments`

| column | type | req | key |
|---|---|---|---|
| payment_id | INTEGER |  | PK |
| patient_id | INTEGER | ✓ | FK → patients |
| encounter_id | INTEGER |  | FK → encounters |
| claim_id | INTEGER |  | FK → claims |
| payment_date | DATE | ✓ |  |
| amount | NUMERIC(10,2) | ✓ |  |
| payment_method | VARCHAR(20) | ✓ |  |
| card_brand | VARCHAR(20) |  |  |
| card_last4 | CHAR(4) |  |  |
| card_exp | CHAR(5) |  |  |
| processor_token | VARCHAR(40) |  |  |
| posted_by_employee_id | INTEGER |  | FK → employees |

### Admin & Security

#### `app_users`

| column | type | req | key |
|---|---|---|---|
| user_id | INTEGER |  | PK |
| username | VARCHAR(40) | ✓ |  |
| display_name | VARCHAR(120) | ✓ |  |
| user_type | VARCHAR(20) | ✓ |  |
| role_id | INTEGER | ✓ | FK → roles |
| is_active | BOOLEAN | ✓ |  |
| mfa_enrolled | BOOLEAN | ✓ |  |
| created_at | TIMESTAMP | ✓ |  |
| last_login_at | TIMESTAMP |  |  |
| password_last_changed | TIMESTAMP |  |  |
| employee_id | INTEGER |  | FK → employees |

#### `roles`

| column | type | req | key |
|---|---|---|---|
| role_id | INTEGER |  | PK |
| role_name | VARCHAR(60) | ✓ |  |
| description | VARCHAR(255) |  |  |

#### `role_permissions`

| column | type | req | key |
|---|---|---|---|
| role_permission_id | INTEGER |  | PK |
| role_id | INTEGER | ✓ | FK → roles |
| resource | VARCHAR(60) | ✓ |  |
| can_read | BOOLEAN | ✓ |  |
| can_write | BOOLEAN | ✓ |  |
| scope | VARCHAR(40) | ✓ |  |

#### `access_audit_log`

| column | type | req | key |
|---|---|---|---|
| audit_id | INTEGER |  | PK |
| user_id | INTEGER | ✓ | FK → app_users |
| patient_id | INTEGER |  | FK → patients |
| access_datetime | TIMESTAMP | ✓ |  |
| action | VARCHAR(20) | ✓ |  |
| resource_type | VARCHAR(40) | ✓ |  |
| resource_id | INTEGER |  |  |
| workstation_id | VARCHAR(30) |  |  |
| ip_address | VARCHAR(45) |  |  |
| access_reason | VARCHAR(80) |  |  |
| break_the_glass | BOOLEAN | ✓ |  |
| flagged_for_review | BOOLEAN | ✓ |  |

## 5. Value rules

Values below were read live with `SELECT DISTINCT` (guarded so high-cardinality columns returned only a
count). **Strict** fields have a clearly closed set and become dropdowns the API enforces. **Suggested**
fields are free text with a `<datalist>` — either high-cardinality, or the live data showed only one value
so the true allowed set is unknown (e.g. `encounters.status` only had "Completed"). A few "strict" lists
with commas inside values (none here) would stay suggested.

**Strict dropdowns** (API rejects other values):

| field | allowed values |
|---|---|
| `access_audit_log.action` | View, Update, Create, Sign |
| `access_audit_log.resource_type` | Demographics, Coverage, Clinical Note, Vitals, Medications, Chart Review, Results, Problem List, Lab Result, Claim, Flowsheet |
| `allergies.allergen_type` | Drug, Food, Environmental |
| `allergies.severity` | Moderate, Severe, Mild |
| `app_users.user_type` | human, service |
| `claims.claim_type` | 837P, 837I |
| `claims.status` | Paid, Appealed, Denied, Submitted, Not Submitted, Pending |
| `employees.employment_status` | Active, Terminated, Leave of Absence |
| `employees.pay_type` | Salary, Hourly |
| `employees.sex` | M, F |
| `encounters.admit_source` | Walk-in, Emergency Department, Elective admission, Physician or clinic referral, Ambulance (EMS) |
| `encounters.discharge_disposition` | Discharged to home or self-care, Discharged to home health, Discharged to skilled nursing facility, Left against medical advice |
| `encounters.encounter_class` | EMER, VR, AMB, IMP |
| `facilities.facility_type` | Acute Care Hospital, Ambulatory Clinic, Urgent Care, Behavioral Health Clinic, Specialty Center |
| `immunizations.route` | Intramuscular, Subcutaneous |
| `immunizations.site` | Left deltoid, Right deltoid, Right vastus lateralis, Left vastus lateralis |
| `insurance_plans.plan_type` | Traditional Medicare, Medicare Advantage HMO, Medicare Advantage PPO, PPO, HDHP, POS, EPO, HMO, Medicaid Managed Care |
| `lab_orders.status` | Final, Preliminary |
| `lab_results.abnormal_flag` | H, A, L, HH |
| `medications.is_controlled_substance` | 0, 1 |
| `medications.route` | oral, sublingual, inhalation, subcutaneous, transdermal, topical, intranasal, ophthalmic, intravenous, intramuscular |
| `medications.status` | Active, Discontinued, Completed |
| `patient_contacts.relationship` | Sister, Friend, Partner, Spouse, Father, Mother, Brother, Daughter, Son, Niece |
| `patient_coverage.relationship_to_subscriber` | Self, Spouse, Child |
| `patient_payments.card_brand` | American Express, Visa, Mastercard, Discover |
| `patient_payments.payment_method` | Credit Card, HSA/FSA Card, ACH, Debit Card, Cash, Check |
| `patients.confidentiality_level` | standard, restricted, vip |
| `patients.ethnicity` | Not Hispanic or Latino, Declined, Hispanic or Latino |
| `patients.gender_identity` | Female, Male, Transgender male, Declined to answer, Non-binary |
| `patients.marital_status` | Divorced, Single, Married, Widowed |
| `patients.preferred_language` | English, Vietnamese, Spanish, Mandarin, Somali, Hindi, Nepali |
| `patients.race` | Asian, Black or African American, White, Two or more races, Patient declined, Other Race, American Indian or Alaska Native |
| `patients.sex_at_birth` | F, M |
| `payers.payer_type` | Medicare, Commercial, Medicaid MCO, Medicare Advantage, Workers Comp |
| `procedures.code_system` | CPT, HCPCS |
| `providers.credential` | DO, MD, APRN-CNP, PA-C, PsyD, LISW-S, LICDC-CS |
| `role_permissions.scope` | assigned_patients, all, own_department, none, deidentified |
| `screenings.instrument` | PHQ-2, GAD-7, AUDIT-C, PHQ-9 |
| `screenings.interpretation` | Negative, Moderate anxiety, Mild anxiety, Positive, Minimal anxiety, Moderately severe depression, Moderate depression, Mild depression, Minimal depression, Severe depression, Severe anxiety |
| `social_history.alcohol_use` | Never, Yes, Not currently |
| `social_history.drug_use` | Never, Yes, Not currently |
| `social_history.sexual_orientation` | Bisexual, Straight or heterosexual, Something else, Choose not to disclose, Don't know, Lesbian or gay |
| `social_history.tobacco_status` | Former smoker, Never smoker, Current every day smoker |

**Free text with suggestions** (datalist; any value accepted):

| field | observed values |
|---|---|
| `allergies.status` | Active  _(data shows only these)_ |
| `clinical_notes.note_type` | ED Provider Note, Progress Note, Urgent Care Note, Radiology Report, Preventive Visit Note, Consult Follow-up Note, Addiction Medicine Progress Note, Discharge Summary, History & Physical, Procedure Note, Psychotherapy Progress Note, Prenatal Visit Note, Postpartum Visit Note, Psychiatric Medication Management Note, Well Child Visit, Oncology Progress Note  _(16 values)_ |
| `departments.specialty` | EM, HOSP, CARD, PULM, NEPH, GSURG, ORTHO, OBGYN, LAB, RAD, ID, NEURO, FM, PEDS, IM, UC, PSYCH, ADDICT, ONC, ENDO, GI, RHEUM  _(22 values)_ |
| `encounter_diagnoses.present_on_admission` | Y  _(data shows only these)_ |
| `encounters.encounter_type` | Emergency, Telehealth Visit, Office Visit, Urgent Care, Imaging, Preventive Visit, Specialty Office Visit, Addiction Medicine Visit, Inpatient, Procedure, Psychotherapy Visit, Prenatal Visit, Postpartum Visit, Psychiatry Visit, Oncology Visit  _(15 values)_ |
| `encounters.status` | Completed  _(data shows only these)_ |
| `facilities.state` | OH  _(data shows only these)_ |
| `lab_orders.panel_name` | CBC with automated differential, Comprehensive metabolic panel, Lipase, Urinalysis, dipstick, automated, Pregnancy test, urine, TSH, Troponin I, high sensitivity, Basic metabolic panel, Lipid panel, Hemoglobin A1c, SARS-CoV-2 RNA, NAA, Urine albumin/creatinine ratio, Rapid strep A antigen, Blood culture, Lactic acid, PSA, total, Urine culture, Vitamin D, 25-hydroxy, Lithium level, Ferritin, Influenza A and B RNA, NAA, HIV-1 RNA quantitative (viral load), CD4 absolute count, NT-proBNP  _(32 values)_ |
| `patient_coverage.coverage_priority` | 1  _(data shows only these)_ |
| `problem_list.status` | Active  _(data shows only these)_ |
| `providers.license_state` | OH  _(data shows only these)_ |
| `providers.specialty` | Family Medicine, Internal Medicine, Pediatrics, Emergency Medicine, Hospitalist, Cardiovascular Disease, Pulmonary Disease, Nephrology, Endocrinology, Diabetes & Metabolism, Gastroenterology, Rheumatology, Hematology & Oncology, Infectious Disease, Neurology, Psychiatry, Addiction Medicine, Obstetrics & Gynecology, Surgery, Orthopaedic Surgery, Diagnostic Radiology, Nurse Practitioner, Family, Nurse Practitioner, Psych/Mental Health, Physician Assistant, Clinical Psychologist, Clinical Social Worker, Addiction Counselor  _(29 values)_ |
| `role_permissions.resource` | clinical, demographics, billing, bh_notes, vitals, coverage, medications, allergies, labs, imaging, audit, configuration, *, analytics  _(14 values)_ |
| `roles.role_name` | Advanced Practice Provider, Behavioral Health Clinician, Billing Specialist, Database Administrator, Executive, HIM Release of Information, IT Application Analyst, Imaging, Laboratory, Medical Assistant, Medical Coder, Patient Access Representative, Pharmacist, Physician, Privacy Officer, Registered Nurse, Service - AI Assistant, Service - Integration  _(18 values)_ |

### Other API validation (400 with a message)
- Required (`NOT NULL`, non-PK) fields present and non-empty.
- Strict-value fields as above.
- Type shape: INTEGER/NUMERIC parse as numbers, BOOLEAN is 0/1, DATE/TIMESTAMP parse as ISO.
- Date pairs: start <= end when both set (`encounters`, `claims.service_date_*`, `patient_coverage`,
  `employees.hire/termination_date`, `medications.start/end_date`, `lab_orders` datetimes).
- FK violations and PK conflicts from SQLite map to 400/409 with a readable message. Lengths not validated.
- No UNIQUE constraints beyond PKs: indexes were never probed, so the DDL declares none and natural keys
  (`mrn`, `csn`, `npi`, `claim_number`, `username`, …) are **not** enforced unique (see §11).

## 6. Delete rules

- **Cascade is done in app code, not DDL** (the DDL stays a verbatim copy, no `ON DELETE CASCADE`). The
  backend holds a small cascade map and, in one transaction, deletes cascaded children before the parent.
- **Cascade** (child rows exist only for their parent):
  - with their patient: `patient_contacts` (by `patient_id`), `patient_coverage`, `allergies`,
    `problem_list`, `social_history`, `medications`, `immunizations`, `patient_payments`
  - `claim_lines` with their claim; `lab_results` with their lab_order; `encounter_diagnoses` with their
    encounter; `role_permissions` with their role
- Everything else is **blocked** if referenced: the API returns 409 with a count message
  (e.g. `"Used by 12 encounters, 3 claims"`), shown as-is. Counts come from the introspected FK list,
  skipping cascaded tables.
- So a patient with any encounter, claim, audit-log row, or who is another patient's
  `related_patient_id`, cannot be deleted; encounter-bound clinical rows (notes, vitals, procedures,
  labs, screenings) are removed by deleting them, then their encounter, first. Audit history is never
  silently deleted.
- The patient delete confirm spells out what cascades: "and their contacts, coverage, allergies,
  problems, social history, medications, immunizations and payments".

## 7. API

All table/column identifiers come from a whitelist built by introspecting `schema.sql` at startup. Values
are always bound parameters.

| method | path | purpose |
|---|---|---|
| GET | `/api/env` | `{env}` |
| GET | `/api/meta` | tables -> columns (type, required, pk, fk target, strict values, suggestions), label recipe, sidebar group |
| GET | `/api/tables/{t}?page=1&q=&sort=&dir=asc` | 50 rows/page, `q` = LIKE over text columns, `{rows,total}`; FK columns also return `<col>_label` |
| GET | `/api/tables/{t}/{pk}` | one row |
| POST | `/api/tables/{t}` | create |
| PUT | `/api/tables/{t}/{pk}` | update (text PK of `chargemaster` not editable) |
| DELETE | `/api/tables/{t}/{pk}` | delete per §6 |
| GET | `/api/options/{t}?q=` | `[{id,label}]`, max 50, for FK dropdowns (searchable) |
| GET | `/api/dashboard` | all chart data in one payload |
| GET | `/api/patients/{id}` | patient detail bundle |

### Row labels (for FK display and dropdowns)
| table | label |
|---|---|
| patients | `last_name, first_name · MRN` |
| employees | `last_name, first_name · job_title` |
| providers | `last_name, first_name · credential` (name joined from `employees` via `employee_id`; providers have no name column) |
| facilities | `name` |
| departments | `department_name` |
| payers | `payer_name` |
| insurance_plans | `plan_name` |
| chargemaster | `charge_code · description` |
| roles | `role_name` |
| app_users | `display_name` |
| encounters | `csn · start date` |
| claims | `claim_number` |
| lab_orders | `accession_number · panel_name` |
| patient_coverage | `plan_name · priority N` |
| others | `#pk` |

## 8. UI

- **Header:** app name + `DEMO`/`PROD` badge.
- **Sidebar:** Dashboard, then the four groups from §4 (Clinical, Organization, Billing, Admin & Security).
- **Generic table view** (one component, driven by `/api/meta`):
  - paged at 50 rows, search box, click-to-sort headers.
  - FK columns show their label, not the id.
  - "Add" and row click open a side form; delete is a button in the form with a confirm; API errors show inline.
  - input by column type: number, date, datetime-local, checkbox (BOOLEAN), select (strict), input+datalist
    (suggested), searchable select (FK), textarea (TEXT).
- **Patient detail** (opens on any patient click): demographics + PCP; then coverages (by priority),
  contacts, allergies, problem_list, social_history, and an encounter timeline; plus clinical_notes (text
  collapsed), medications, immunizations, procedures, lab_orders→results, vitals, screenings, claims,
  patient_payments. All as read-only sections with a link into the generic editor.
- **Dashboard** (Recharts):
  1. KPI tiles: patients, encounters, providers, employees, facilities, open claims.
  2. Encounters per month, line per `encounter_class` (labels: AMB→Ambulatory, EMER→Emergency, IMP→Inpatient, VR→Virtual).
  3. Encounters by department (bar).
  4. Encounters by type, top 10 (bar).
  5. Patients by payer, primary coverage only (`coverage_priority = 1`) (bar).
  6. Plan type mix (donut).
  7. Claims by status (bar).
  8. Charged vs paid by payer (grouped bar, `claims.total_charge` vs `paid_amount`).
  9. Top problem_list ICD-10 descriptions (bar).
- Empty DB (prod): charts show an empty state; tables show "No rows yet — Add".

## 9. Demo seed (`seed.py`)

- Fixed random seed, deterministic. Drops and recreates `demo.db`; refuses prod (§3).
- Obvious fakes only: NPI `999…`, MRN `DEMO000123`, employee_number `DEMO…`, CSN `DEMO-…`, claim numbers
  `DEMO-CLM-…`, emails `@example.org`, phones `555-01xx`, SSN `900-xx-xxxx`, card last4 `0000`, routing
  `000000000`, DEA `X9999999`. Ohio addresses/counties (Scioto Ridge Health). Category values from §5.
- Inserts respect FK order and the cascades in §6. Rough sizes (small but enough for every chart):

| group | tables & counts |
|---|---|
| Org | 4 facilities, 12 departments, 40 employees, 20 providers (each linked to an employee) |
| Security | 12 roles, ~30 role_permissions, 20 app_users |
| Patients | 60 patients, ~80 patient_contacts, 4 payers, 8 insurance_plans, ~90 patient_coverage |
| Encounters | 250 encounters (last 12 mo) + per-encounter: diagnoses, notes, some vitals |
| Clinical | ~70 allergies, ~90 problem_list, 60 social_history, ~120 medications, ~80 immunizations, ~100 procedures, ~120 lab_orders → ~300 lab_results, ~80 screenings |
| Billing | ~150 claims, ~400 claim_lines, 20 chargemaster, ~120 patient_payments |
| Audit | ~500 access_audit_log |

## 10. Tests (`backend/test_app.py`)

Against a temp DB:
- CRUD round-trip on `patients` (create → read → update → delete).
- Strict-value rejection (e.g. `sex_at_birth = "X"` → 400).
- FK delete block: a patient with an encounter → 409 with count message.
- Cascade: deleting a patient with no encounters/claims removes their contacts, coverage, allergies,
  problems, social history, meds, immunizations and payments.
- Unknown table / sort column → 404 or 400 (whitelist).
- `seed.py` refuses `APP_ENV=prod`.
- Seeded demo: `/api/dashboard` returns non-empty series.

## 11. Open risks

- Schema is faithful to the live DB as probed, but a few `group_concat` reads can drop a column if the DB
  changes; re-probe `pragma_table_info` at build time to be safe. (`app_users.employee_id` was recovered
  from the FK list after one such drop.)
- "Suggested" enum fields may have more allowed values than the live data showed; the app accepts any text
  there, so this is safe.
- `providers` has no name — all provider labels come from the joined `employees` row.
- UNIQUE indexes on the real DB are unknown (`pragma_index_list` never run). If a re-probe finds any,
  copy them into the DDL and map the violation to 409.
