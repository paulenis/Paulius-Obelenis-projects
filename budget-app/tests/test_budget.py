from pathlib import Path

import pytest

from budget import db
from budget.classify import EXPENSE, INCOME, TRANSFER, import_transactions
from budget.parser import ParseError, parse_swedbank_csv

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return parse_swedbank_csv((FIXTURES / name).read_bytes())


def test_parser_reads_only_transactions_with_signed_amounts():
    txs = load("card.csv")
    assert [t.ref for t in txs] == ["1001", "1002", "1003", "1004"]
    assert txs[0].amount == -21.76
    assert txs[2].amount == 84.15
    assert txs[0].counterparty == "MAXIMA/X-020 MAXIMA"


def test_card_purchase_uses_real_purchase_date():
    maxima, wolt, payoff, refund = load("card.csv")
    assert maxima.date.isoformat() == "2026-09-02"
    assert maxima.booking_date.isoformat() == "2026-10-01"
    assert payoff.date == payoff.booking_date  # ne kortelės pirkinys


def test_semicolon_and_cp1257_are_supported():
    text = (FIXTURES / "card.csv").read_text("utf-8").replace('","', '";"')
    txs = parse_swedbank_csv(text.encode("cp1257"))
    assert len(txs) == 4 and txs[1].amount == -62.39


def test_rejects_non_swedbank_file():
    with pytest.raises(ParseError):
        parse_swedbank_csv(b"foo,bar\n1,2\n")


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.set_setting(c, "household_names", "Jonas Jonaitis, Ona Jonaitiene")
    yield c
    c.close()


def kinds(conn):
    return {r["ref"]: (r["kind"], r["category"]) for r in conn.execute("SELECT * FROM transactions")}


def test_import_is_idempotent(conn):
    first = import_transactions(conn, load("card.csv"))
    again = import_transactions(conn, load("card.csv"))
    assert first == {"added": 4, "skipped": 0}
    assert again == {"added": 0, "skipped": 4}


def test_transfers_and_credit_payoff_are_excluded(conn):
    for name in ("card.csv", "current.csv", "wife.csv"):
        import_transactions(conn, load(name))
    k = kinds(conn)
    # kredito padengimas abiejose pusėse
    assert k["1003"][0] == TRANSFER and k["2005"][0] == TRANSFER
    # pervedimas žmonai ir jos gautas (vardas atvirkštine tvarka)
    assert k["2002"][0] == TRANSFER and k["3001"][0] == TRANSFER
    # "Sutaupyk" nėra šeimos narys, bet rasta pora kitoje sąskaitoje
    assert k["2004"][0] == TRANSFER and k["3002"][0] == TRANSFER
    # tikros pajamos ir išlaidos
    assert k["2001"] == (INCOME, "Atlyginimas")
    assert k["1001"] == (EXPENSE, "Maisto prekės")
    assert k["1002"] == (EXPENSE, "Kavinės ir maistas išsinešti")
    assert k["2003"] == (EXPENSE, "Draudimas")
    # kortelės grąžinimas mažina išlaidas, o ne didina pajamas
    assert k["1004"][0] == EXPENSE

    sept = conn.execute(
        "SELECT kind, ROUND(SUM(amount), 2) AS s FROM transactions "
        "WHERE date LIKE '2026-09%' GROUP BY kind").fetchall()
    sums = {r["kind"]: r["s"] for r in sept}
    assert sums[INCOME] == 2000.00
    assert sums[EXPENSE] == round(-21.76 - 62.39 - 16.44 - 30.36, 2)  # grąžinimas spalį


def test_user_rule_overrides_builtin(conn):
    conn.execute("INSERT INTO rules(pattern, kind, category) VALUES ('ERGO', 'expense', 'Gyvybės draudimas')")
    import_transactions(conn, load("current.csv"))
    assert kinds(conn)["2003"] == (EXPENSE, "Gyvybės draudimas")
