"""Swedbank (Lietuva) CSV išrašo parseris.

Swedbank eksportuoja failą su stulpeliais:
  Sąskaitos Nr., Įrašo tipas, Data, Gavėjas, Paaiškinimai, Suma, Valiuta,
  D/K, Įrašo Nr., Kodas, ...

Įrašo tipai: 10 = pradinis likutis, 20 = sandoris, 82 = apyvarta,
86 = galutinis likutis. Importuojami tik tipo 20 įrašai.
D/K: D = pinigai išėjo (debetas), K = pinigai atėjo (kreditas).
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date

TRANSACTION_RECORD = "20"

# "PIRKINYS 554980******7005 2026.09.01 20.99 EUR (...)" - kortelės pirkinio
# tikroji data (išraše "Data" gali būti nurašymo data, net mėnesiu vėliau).
_PURCHASE_DATE = re.compile(r"\b(\d{4})\.(\d{2})\.(\d{2})\b")


@dataclass
class Transaction:
    account: str
    date: date            # tikroji operacijos data (pirkinio data, jei žinoma)
    booking_date: date    # data iš išrašo
    counterparty: str
    description: str
    amount: float         # su ženklu: neigiama = išlaida, teigiama = įplaukos
    currency: str
    code: str             # Swedbank operacijos kodas (MK = pavedimas, K = kortelė ...)
    ref: str              # Įrašo Nr. (unikalus banko numeris)

    @property
    def fingerprint(self) -> str:
        """Unikalus sandorio parašas dublikatams atpažinti."""
        if self.ref:
            return f"{self.account}|{self.ref}"
        raw = "|".join([
            self.account, self.booking_date.isoformat(), f"{self.amount:.2f}",
            self.counterparty, self.description,
        ])
        return "h:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()


class ParseError(ValueError):
    pass


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1257"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("Nepavyko nuskaityti failo koduotės")


def _parse_amount(value: str) -> float:
    value = value.strip().replace(" ", "").replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", ".")
    return float(value)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip()[:10].replace(".", "-"))


def _purchase_date(description: str, booking: date) -> date:
    if not description.upper().startswith("PIRKINYS"):
        return booking
    match = _PURCHASE_DATE.search(description)
    if not match:
        return booking
    try:
        found = date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return booking
    # Apsauga nuo atsitiktinių skaičių aprašyme.
    return found if found <= booking and (booking - found).days <= 62 else booking


def parse_swedbank_csv(data: bytes | str) -> list[Transaction]:
    text = _decode(data) if isinstance(data, bytes) else data
    first_line = text.splitlines()[0] if text else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows or not rows[0] or "skaitos" not in rows[0][0]:
        raise ParseError("Tai neatrodo kaip Swedbank išrašas (CSV)")

    transactions = []
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) < 10 or row[1].strip() != TRANSACTION_RECORD:
            continue
        try:
            booking = _parse_date(row[2])
            amount = _parse_amount(row[5])
        except ValueError as exc:
            raise ParseError(f"Klaida {line_no} eilutėje: {exc}") from exc
        direction = row[7].strip().upper()
        if direction not in ("D", "K"):
            raise ParseError(f"Klaida {line_no} eilutėje: nežinomas D/K '{row[7]}'")
        description = row[4].strip()
        transactions.append(Transaction(
            account=row[0].strip(),
            date=_purchase_date(description, booking),
            booking_date=booking,
            counterparty=" ".join(row[3].split()),
            description=" ".join(description.split()),
            amount=-amount if direction == "D" else amount,
            currency=row[6].strip(),
            code=row[9].strip(),
            ref=row[8].strip(),
        ))
    return transactions
