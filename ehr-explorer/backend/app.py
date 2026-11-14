"""EHR Explorer backend. Spec: ../docs/SPEC.md"""
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import rules

HERE = Path(__file__).parent
DATA = HERE.parent / "data"
ENV = os.environ.get("APP_ENV", "demo")
DB_PATH = DATA / f"{ENV}.db"
META: dict = {}

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if missing, then rebuild META (the identifier whitelist) from the live schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    group_of = {t: g for g, ts in rules.GROUPS.items() for t in ts}
    with connect() as conn:
        conn.executescript((HERE / "schema.sql").read_text())
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        META.clear()
        for t in tables:
            fks = {r["from"]: r["table"] for r in conn.execute("SELECT * FROM pragma_foreign_key_list(?)", (t,))}
            cols = []
            for r in conn.execute("SELECT * FROM pragma_table_info(?)", (t,)):
                key = f"{t}.{r['name']}"
                cols.append({"name": r["name"], "type": r["type"], "required": bool(r["notnull"]), "pk": bool(r["pk"]),
                             "fk": fks.get(r["name"]), "strict": rules.STRICT.get(key), "suggest": rules.SUGGEST.get(key)})
            META[t] = {"pk": next(c["name"] for c in cols if c["pk"]), "columns": cols, "group": group_of[t]}


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/env")
def env():
    return {"env": ENV}


@app.get("/api/meta")
def meta():
    return {"tables": META, "groups": rules.GROUPS}
