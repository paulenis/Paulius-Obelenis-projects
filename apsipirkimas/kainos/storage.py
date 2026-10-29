"""SQLite storage: collection runs, products per run and the shared shopping list."""

import json
import sqlite3
import threading
from pathlib import Path

from .models import normalize

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "kainos.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,          -- 'running' | 'ok' | 'rejected' | 'failed'
    product_count INTEGER DEFAULT 0,
    message TEXT,
    raw_dir TEXT
);
CREATE TABLE IF NOT EXISTS products (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    chain TEXT NOT NULL,
    source_id TEXT NOT NULL,
    name TEXT NOT NULL,
    search_name TEXT NOT NULL,
    price REAL NOT NULL,
    old_price REAL,
    unit_price REAL,
    unit TEXT,
    card TEXT,
    promo TEXT,
    valid_from TEXT,
    valid_to TEXT,
    url TEXT,
    category TEXT,
    extra TEXT,
    PRIMARY KEY (run_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_products_run ON products(run_id);
CREATE TABLE IF NOT EXISTS list_items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    chain TEXT,
    product_key TEXT,
    price REAL,
    unit_price REAL,
    unit TEXT,
    card TEXT,
    valid_to TEXT,
    loose INTEGER DEFAULT 0,       -- sold by weight: quantity in kg
    qty REAL NOT NULL DEFAULT 1,
    done INTEGER NOT NULL DEFAULT 0,
    added_by TEXT,
    deleted INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL    -- client clock in ms, last write wins
);
"""

LIST_FIELDS = ["id", "name", "chain", "product_key", "price", "unit_price", "unit", "card",
               "valid_to", "loose", "qty", "done", "added_by", "deleted", "updated_at"]

_lock = threading.Lock()


def connect(path=None):
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --- collection runs -------------------------------------------------------

def start_run(conn, chain, started_at, raw_dir):
    with _lock, conn:
        cur = conn.execute(
            "INSERT INTO runs (chain, started_at, status, raw_dir) VALUES (?, ?, 'running', ?)",
            (chain, started_at, str(raw_dir)))
        return cur.lastrowid


def finish_run(conn, run_id, status, finished_at, count=0, message=None):
    with _lock, conn:
        conn.execute(
            "UPDATE runs SET status=?, finished_at=?, product_count=?, message=? WHERE id=?",
            (status, finished_at, count, message, run_id))


def save_products(conn, run_id, products):
    rows = [(run_id, p.chain, p.source_id, p.name, normalize(p.name), p.price, p.old_price,
             p.unit_price, p.unit, p.card, p.promo, p.valid_from, p.valid_to, p.url,
             p.category, json.dumps(p.extra, ensure_ascii=False) if p.extra else None)
            for p in products]
    with _lock, conn:
        conn.executemany(
            "INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def last_ok_run(conn, chain):
    return conn.execute(
        "SELECT * FROM runs WHERE chain=? AND status='ok' ORDER BY id DESC LIMIT 1",
        (chain,)).fetchone()


def last_run(conn, chain):
    return conn.execute(
        "SELECT * FROM runs WHERE chain=? ORDER BY id DESC LIMIT 1", (chain,)).fetchone()


def prune_runs(conn, chain, keep=6):
    """Drop products of old runs so the database stays small (runs rows are kept)."""
    old = conn.execute(
        "SELECT id FROM runs WHERE chain=? AND status='ok' ORDER BY id DESC LIMIT -1 OFFSET ?",
        (chain, keep)).fetchall()
    with _lock, conn:
        conn.executemany("DELETE FROM products WHERE run_id=?", [(r["id"],) for r in old])


# --- search ----------------------------------------------------------------

def current_run_ids(conn):
    rows = conn.execute(
        "SELECT chain, MAX(id) AS id FROM runs WHERE status='ok' GROUP BY chain").fetchall()
    return {r["chain"]: r["id"] for r in rows}


def search(conn, query, limit=60, today=None):
    words = [w for w in normalize(query).split() if w]
    run_ids = list(current_run_ids(conn).values())
    if not words or not run_ids:
        return []
    sql = f"SELECT * FROM products WHERE run_id IN ({','.join('?' * len(run_ids))})"
    params = list(run_ids)
    for w in words:
        sql += " AND search_name LIKE ?"
        params.append(f"%{w}%")
    if today:
        sql += " AND (valid_to IS NULL OR valid_to >= ?)"
        params.append(today)
    sql += " ORDER BY unit_price IS NULL, unit_price, price LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# --- shopping list ---------------------------------------------------------

def list_items(conn):
    rows = conn.execute("SELECT * FROM list_items ORDER BY updated_at").fetchall()
    return [dict(r) for r in rows]


def merge_list_items(conn, items):
    """Last write wins per item, by the client's `updated_at` timestamp."""
    with _lock, conn:
        for item in items:
            if not item.get("id") or not item.get("name"):
                continue
            row = conn.execute("SELECT updated_at FROM list_items WHERE id=?", (item["id"],)).fetchone()
            if row and row["updated_at"] >= int(item.get("updated_at") or 0):
                continue
            values = [item.get(f) for f in LIST_FIELDS]
            values[LIST_FIELDS.index("qty")] = float(item.get("qty") or 1)
            values[LIST_FIELDS.index("updated_at")] = int(item.get("updated_at") or 0)
            for flag in ("loose", "done", "deleted"):
                values[LIST_FIELDS.index(flag)] = 1 if item.get(flag) else 0
            conn.execute(
                f"INSERT OR REPLACE INTO list_items ({','.join(LIST_FIELDS)}) "
                f"VALUES ({','.join('?' * len(LIST_FIELDS))})", values)
