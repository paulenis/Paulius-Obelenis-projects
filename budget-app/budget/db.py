import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    iban    TEXT PRIMARY KEY,
    label   TEXT NOT NULL DEFAULT '',
    owner   TEXT NOT NULL DEFAULT '',
    kind    TEXT NOT NULL DEFAULT 'einamoji'   -- einamoji | kredito
);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY,
    fingerprint   TEXT NOT NULL UNIQUE,
    account       TEXT NOT NULL REFERENCES accounts(iban),
    date          TEXT NOT NULL,
    booking_date  TEXT NOT NULL,
    counterparty  TEXT NOT NULL,
    description   TEXT NOT NULL,
    amount        REAL NOT NULL,
    currency      TEXT NOT NULL,
    code          TEXT NOT NULL,
    ref           TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'expense',  -- income | expense | transfer
    category      TEXT NOT NULL DEFAULT '',
    reason        TEXT NOT NULL DEFAULT '',         -- kodėl taip klasifikuota
    locked        INTEGER NOT NULL DEFAULT 0,       -- 1 = pataisyta rankiniu būdu
    pair_id       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);

CREATE TABLE IF NOT EXISTS rules (
    id        INTEGER PRIMARY KEY,
    pattern   TEXT NOT NULL,          -- tekstas, ieškomas gavėjo arba aprašymo lauke
    kind      TEXT,                   -- NULL = nekeisti tipo
    category  TEXT                    -- NULL = nekeisti kategorijos
);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def household_names(conn: sqlite3.Connection) -> list[str]:
    raw = get_setting(conn, "household_names")
    return [n.strip() for n in raw.split(",") if n.strip()]
