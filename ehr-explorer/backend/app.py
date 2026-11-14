"""EHR Explorer backend. Spec: ../docs/SPEC.md"""
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException

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


PAGE = 50


def tmeta(t: str) -> dict:
    if t not in META:
        raise HTTPException(404, f"Unknown table {t}")
    return META[t]


def kind(typ: str) -> str:
    typ = typ.upper()
    for k in ("INT", "NUMERIC", "BOOLEAN", "TIMESTAMP", "DATE", "TEXT"):
        if k in typ:
            return k
    return "TEXT"  # VARCHAR / CHAR


def like(q: str) -> str:
    """Substring LIKE pattern with %, _ and \\ matched literally (use with ESCAPE '\\')."""
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def label_sql(t: str) -> str:
    return rules.LABELS.get(t, f"'#'||x.{META[t]['pk']}")


def parse(col: dict, v):
    """Coerce one value to its column type, or raise ValueError."""
    k = kind(col["type"])
    if k == "BOOLEAN":
        if v in (True, False, 0, 1, "0", "1", "true", "false"):
            return int(v in (True, 1, "1", "true"))
        raise ValueError
    if k == "INT":
        if isinstance(v, bool) or (isinstance(v, float) and not v.is_integer()):
            raise ValueError
        return int(v)
    if k == "NUMERIC":
        if isinstance(v, bool):
            raise ValueError
        return float(v)
    if k == "DATE":
        return date.fromisoformat(str(v)).isoformat()
    if k == "TIMESTAMP":
        return datetime.fromisoformat(str(v)).isoformat()
    return str(v)


def validate(t: str, row: dict) -> dict:
    """Return the cleaned full row or raise 400. `row` is the whole row (merged for updates)."""
    m = tmeta(t)
    cols = {c["name"]: c for c in m["columns"]}
    if unknown := set(row) - set(cols):
        raise HTTPException(400, f"Unknown field(s): {', '.join(sorted(unknown))}")
    out = {}
    for name, col in cols.items():
        v = row.get(name)
        if isinstance(v, str) and v.strip() == "":
            v = None
        if v is not None:
            try:
                v = parse(col, v)
            except (ValueError, TypeError):
                raise HTTPException(400, f"{name}: not a valid {col['type']}")
        auto_pk = col["pk"] and kind(col["type"]) == "INT"
        if v is None and (col["required"] or col["pk"]) and not auto_pk:
            raise HTTPException(400, f"{name} is required")
        if v is not None and col["strict"] and str(v) not in col["strict"]:
            raise HTTPException(400, f"{name} must be one of: {', '.join(col['strict'])}")
        out[name] = v
    for a, b in rules.DATE_PAIRS.get(t, []):
        if out[a] and out[b] and out[b] < out[a]:
            raise HTTPException(400, f"{b} must not be before {a}")
    return out


def write(conn, sql: str, args) -> sqlite3.Cursor:
    try:
        return conn.execute(sql, args)
    except sqlite3.IntegrityError as e:
        msg = str(e)
        if "FOREIGN KEY" in msg:
            raise HTTPException(400, "A referenced record does not exist")
        raise HTTPException(409, f"Conflict: {msg}")


def fetch(conn, t: str, pk) -> dict:
    r = conn.execute(f"SELECT * FROM {t} WHERE {META[t]['pk']} = ?", (pk,)).fetchone()
    if r is None:
        raise HTTPException(404, "Not found")
    return dict(r)


@app.get("/api/tables/{t}")
def list_rows(t: str, page: int = 1, q: str = "", sort: str = "", dir: str = "asc"):
    m = tmeta(t)
    names = [c["name"] for c in m["columns"]]
    if sort and sort not in names or dir not in ("asc", "desc"):
        raise HTTPException(400, "Bad sort")
    where, args = "", []
    if q:
        text = [c["name"] for c in m["columns"] if kind(c["type"]) == "TEXT"]
        pat = like(q)
        where = "WHERE " + " OR ".join(f"r.{c} LIKE ? ESCAPE '\\'" for c in text)
        args = [pat] * len(text)
    labels = "".join(f", (SELECT {label_sql(c['fk'])} FROM {c['fk']} x WHERE x.{META[c['fk']]['pk']} = r.{c['name']}) AS {c['name']}_label"
                     for c in m["columns"] if c["fk"])
    order = f"ORDER BY r.{sort or m['pk']} {dir}"
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM {t} r {where}", args).fetchone()[0]
        rows = conn.execute(f"SELECT r.*{labels} FROM {t} r {where} {order} LIMIT ? OFFSET ?",
                            args + [PAGE, (max(page, 1) - 1) * PAGE]).fetchall()
    return {"rows": [dict(r) for r in rows], "total": total}


@app.get("/api/tables/{t}/{pk}")
def get_row(t: str, pk: str):
    tmeta(t)
    with connect() as conn:
        return fetch(conn, t, pk)


@app.post("/api/tables/{t}", status_code=201)
def create_row(t: str, body: dict = Body(...)):
    row = {k: v for k, v in validate(t, body).items() if v is not None}
    with connect() as conn:
        cur = write(conn, f"INSERT INTO {t} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
        pk = row.get(META[t]["pk"], cur.lastrowid)
        return fetch(conn, t, pk)


@app.put("/api/tables/{t}/{pk}")
def update_row(t: str, pk: str, body: dict = Body(...)):
    pkcol = tmeta(t)["pk"]
    with connect() as conn:
        old = fetch(conn, t, pk)
        if pkcol in body and str(body[pkcol]) != str(old[pkcol]):
            raise HTTPException(400, f"{pkcol} cannot be changed")
        row = validate(t, old | body)
        sets = [c for c in row if c != pkcol]
        write(conn, f"UPDATE {t} SET {', '.join(f'{c} = ?' for c in sets)} WHERE {pkcol} = ?",
              [row[c] for c in sets] + [old[pkcol]])
        return fetch(conn, t, old[pkcol])


def blockers(conn, t: str, pk) -> list[tuple[str, int]]:
    """Non-cascaded rows referencing t[pk], as (table, count) with count > 0."""
    skip = set(rules.CASCADE.get(t, []))
    counts: dict[str, int] = {}
    for child, m in META.items():
        for c in m["columns"]:
            if c["fk"] == t and (child, c["name"]) not in skip:
                n = conn.execute(f"SELECT COUNT(*) FROM {child} WHERE {c['name']} = ?", (pk,)).fetchone()[0]
                if n:
                    counts[child] = counts.get(child, 0) + n
    return list(counts.items())


@app.delete("/api/tables/{t}/{pk}")
def delete_row(t: str, pk: str):
    pkcol = tmeta(t)["pk"]
    with connect() as conn:
        pk = fetch(conn, t, pk)[pkcol]
        if used := blockers(conn, t, pk):
            raise HTTPException(409, "Used by " + ", ".join(f"{n} {child}" for child, n in used))
        try:
            for child, col in rules.CASCADE.get(t, []):
                conn.execute(f"DELETE FROM {child} WHERE {col} = ?", (pk,))
            conn.execute(f"DELETE FROM {t} WHERE {pkcol} = ?", (pk,))
        except sqlite3.IntegrityError:
            # a cascaded child is still referenced elsewhere; the `with` block rolls everything back
            raise HTTPException(409, "Still referenced by other records")
    return {"deleted": pk}


@app.get("/api/options/{t}")
def options(t: str, q: str = ""):
    pk = tmeta(t)["pk"]
    pat = like(q)
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM (SELECT x.{pk} AS id, {label_sql(t)} AS label FROM {t} x) "
                            f"WHERE label LIKE ? ESCAPE '\\' ORDER BY label LIMIT 50", (pat,)).fetchall()
    return [dict(r) for r in rows]
