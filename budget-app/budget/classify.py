"""Sandorių klasifikavimas: pajamos / išlaidos / pervedimas ir kategorija.

Pervedimai (tarp savo ar sutuoktinio sąskaitų, kredito kortelės padengimas)
saugomi, bet į pajamų ir išlaidų sumas neįskaičiuojami.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date

from .db import household_names
from .parser import Transaction

INCOME, EXPENSE, TRANSFER = "income", "expense", "transfer"
KIND_LABELS = {INCOME: "Pajamos", EXPENSE: "Išlaidos", TRANSFER: "Pervedimas"}
TRANSFER_CATEGORY = "Pervedimai"
DEFAULT_EXPENSE = "Kita"
DEFAULT_INCOME = "Kitos pajamos"
CARD_CODE = "K"
PAIR_MAX_DAYS = 3

# Aprašymo frazės, kurios visada reiškia pervedimą tarp savų sąskaitų.
TRANSFER_PHRASES = [
    "KREDITO PADENGIMAS",
    "KORTELES PADENGIMAS",
    "KREDITO KORTELES PADENGIMAS",
    "TARP SAVO SASKAITU",
]

# Įtaisytos kategorijų taisyklės (pirma tinkama laimi). Naudotojo taisyklės
# tikrinamos anksčiau už šias.
BUILTIN_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Kavinės ir maistas išsinešti", [
        "WOLT", "BOLT FOOD", "KAVINE", "RESTORAN", "CAFE", "PICER", "PIZZ",
        "CHARLIE", "MCDONALD", "HESBURGER", "COFFEE", "VERO CAFFE", "CAIF",
    ]),
    ("Maisto prekės", [
        "MAXIMA", "IKI", "RIMI", "LIDL", "NORFA", "AIBE", "PROMO CASH",
        "ARIMEX",
    ]),
    ("Transportas", [
        "ORLEN", "CIRCLE K", "VIADA", "NESTE", "BOLT", "UBER", "TRAFI",
        "VVT", "PARKAVIM", "UNIPARK", "CITYBEE", "LTG",
    ]),
    ("Draudimas", [
        "ERGO", "BTA", "LIETUVOS DRAUDIMAS", "GJENSIDIGE", "COMPENSA", "IF P&C",
    ]),
    ("Būstas ir komunaliniai", [
        "IGNITIS", "ELEKTRUM", "ENEFIT", "VILNIAUS VANDENYS", "VILNIAUS ENERGIJA",
        "TELIA", "BITE", "TELE2", "CGATES", "BUSTO ADMINISTR",
    ]),
    ("Sveikata", [
        "VAISTINE", "EUROVAISTINE", "CAMELIA", "GINTARINE", "BENU", "KLINIK",
    ]),
    ("Namai", ["SENUKAI", "IKEA", "ERMITAZAS", "JYSK", "MOKI VEZI", "DEPO"]),
    ("Prenumeratos", [
        "NETFLIX", "SPOTIFY", "APPLE.COM", "GOOGLE", "YOUTUBE", "DISNEY", "GO3",
    ]),
    ("Pramogos ir laisvalaikis", [
        "APZVALGOS", "KINO", "FORUM CINEMAS", "BILIETAI", "PARKA", "BOULING",
    ]),
    ("Atlyginimas", ["ATLYGINIM", "DARBO UZMOKES", "DU UZ"]),
]

ALL_CATEGORIES = sorted(
    {name for name, _ in BUILTIN_CATEGORIES}
    | {DEFAULT_EXPENSE, DEFAULT_INCOME, TRANSFER_CATEGORY}
)


def normalize(text: str) -> str:
    """Didžiosios raidės be diakritikų: 'Sąskaitų' -> 'SASKAITU'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def _matches(pattern: str, text: str) -> bool:
    return re.search(r"(?<![A-Z0-9])" + re.escape(normalize(pattern)), text) is not None


def _name_tokens(name: str) -> frozenset[str]:
    return frozenset(normalize(name).split())


def classify(tx: Transaction, names: list[str], user_rules: list[sqlite3.Row]) -> tuple[str, str, str]:
    """Grąžina (tipas, kategorija, priežastis)."""
    haystack = normalize(f"{tx.counterparty} {tx.description}")
    kind = category = None
    reason = ""

    for rule in user_rules:
        if _matches(rule["pattern"], haystack):
            kind = kind or rule["kind"]
            category = category or rule["category"]
            reason = reason or f"taisyklė „{rule['pattern']}“"
            if kind and category:
                break

    if kind is None:
        if any(phrase in haystack for phrase in TRANSFER_PHRASES):
            kind, reason = TRANSFER, reason or "savų sąskaitų pervedimas / kredito padengimas"
        elif tx.counterparty and _name_tokens(tx.counterparty) in {_name_tokens(n) for n in names}:
            kind, reason = TRANSFER, reason or "pervedimas šeimos nariui"
        elif tx.amount < 0 or tx.code == CARD_CODE:
            # Teigiama suma su kortelės kodu = grąžinimas, mažina išlaidas.
            kind = EXPENSE
        else:
            kind = INCOME

    if kind == TRANSFER:
        return kind, TRANSFER_CATEGORY, reason

    if category is None:
        for name, patterns in BUILTIN_CATEGORIES:
            if any(_matches(p, haystack) for p in patterns):
                category = name
                break
    if category is None:
        category = DEFAULT_INCOME if kind == INCOME else DEFAULT_EXPENSE
    return kind, category, reason


def _row_to_tx(row: sqlite3.Row) -> Transaction:
    return Transaction(
        account=row["account"], date=date.fromisoformat(row["date"]),
        booking_date=date.fromisoformat(row["booking_date"]),
        counterparty=row["counterparty"], description=row["description"],
        amount=row["amount"], currency=row["currency"], code=row["code"], ref=row["ref"],
    )


def reclassify_all(conn: sqlite3.Connection) -> None:
    """Perskaičiuoja visus ne rankiniu būdu pataisytus sandorius."""
    names = household_names(conn)
    rules = conn.execute("SELECT * FROM rules ORDER BY id").fetchall()
    conn.execute("UPDATE transactions SET pair_id = NULL WHERE locked = 0")
    for row in conn.execute("SELECT * FROM transactions WHERE locked = 0").fetchall():
        kind, category, reason = classify(_row_to_tx(row), names, rules)
        conn.execute(
            "UPDATE transactions SET kind = ?, category = ?, reason = ? WHERE id = ?",
            (kind, category, reason, row["id"]),
        )
    match_transfer_pairs(conn)


def match_transfer_pairs(conn: sqlite3.Connection) -> None:
    """Randa pervedimus tarp dviejų savų sąskaitų: ta pati suma priešingu ženklu,
    skirtingose sąskaitose, per kelias dienas. Kortelės pirkiniai nedalyvauja."""
    rows = conn.execute(
        "SELECT id, account, date, amount, kind, pair_id FROM transactions "
        "WHERE locked = 0 AND code != ? ORDER BY date, id", (CARD_CODE,),
    ).fetchall()
    paired: set[int] = {r["id"] for r in rows if r["pair_id"] is not None}
    outgoing = [r for r in rows if r["amount"] < 0]
    incoming = [r for r in rows if r["amount"] > 0]
    for out in outgoing:
        if out["id"] in paired:
            continue
        out_date = date.fromisoformat(out["date"])
        best = None
        for inc in incoming:
            if inc["id"] in paired or inc["account"] == out["account"]:
                continue
            if abs(inc["amount"] + out["amount"]) > 0.005:
                continue
            gap = abs((date.fromisoformat(inc["date"]) - out_date).days)
            if gap <= PAIR_MAX_DAYS and (best is None or gap < best[0]):
                best = (gap, inc)
        if best is None:
            continue
        inc = best[1]
        paired.update((out["id"], inc["id"]))
        for this, other in ((out, inc), (inc, out)):
            conn.execute(
                "UPDATE transactions SET kind = ?, category = ?, pair_id = ?, "
                "reason = 'rasta pora kitoje savo sąskaitoje' WHERE id = ?",
                (TRANSFER, TRANSFER_CATEGORY, other["id"], this["id"]),
            )


def import_transactions(conn: sqlite3.Connection, transactions: list[Transaction]) -> dict:
    """Įrašo naujus sandorius (dublikatus praleidžia) ir perklasifikuoja."""
    added = skipped = 0
    for tx in transactions:
        conn.execute("INSERT OR IGNORE INTO accounts(iban) VALUES (?)", (tx.account,))
        cur = conn.execute(
            "INSERT OR IGNORE INTO transactions(fingerprint, account, date, booking_date, "
            "counterparty, description, amount, currency, code, ref) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tx.fingerprint, tx.account, tx.date.isoformat(), tx.booking_date.isoformat(),
             tx.counterparty, tx.description, tx.amount, tx.currency, tx.code, tx.ref),
        )
        if cur.rowcount:
            added += 1
        else:
            skipped += 1
    reclassify_all(conn)
    conn.commit()
    return {"added": added, "skipped": skipped}
