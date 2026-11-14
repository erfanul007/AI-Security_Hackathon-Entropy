# EHR Explorer

Local browser for data shaped like the Scioto Ridge Health EHR: the real 30-table schema, generic create/edit/delete
on every table, a patient chart and a dashboard. All data is synthetic. Spec: [docs/SPEC.md](docs/SPEC.md).

## Run

```bash
cd backend
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once
.venv/bin/python seed.py                                                # (re)build demo data
cd ../frontend && npm install && npm run build && cd ../backend         # once, or after UI changes
.venv/bin/uvicorn app:app --port 8000                                   # http://localhost:8000
```

For UI development, run `npm run dev` in `frontend/` instead (http://localhost:5173, proxies `/api`).
Tests: `cd backend && .venv/bin/pytest -q`.

## Demo walkthrough (about 3 minutes)

1. **Dashboard**: counts, a year of encounters by class, payer mix, claim status, and charged versus paid.
2. **DEMO / PROD** dropdown in the header: switch to PROD to show the empty database, then switch back.
3. **Patients**: search a last name, click a row to open the chart. It shows demographics, coverage,
   problems, encounters, collapsible notes, labs with H/L flags against the reference range, vitals and claims.
4. Click **edit** on any row in the chart. The side form shows names for linked records, dropdowns for fixed
   value sets and inline validation (clear a required field and save). Closing it returns to the chart.
5. Delete a seeded patient. It is refused with "Used by …" because clinical and audit history is never cascaded.
   Add a new patient and delete it; that works.

Every screen has its own URL (`#/patients`, `#/patient/37`, `#/encounters/edit/1`), so Back/Forward and reload work.
