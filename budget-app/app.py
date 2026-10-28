"""Šeimos biudžeto programėlė: Swedbank išrašų importas ir suvestinės.

Paleidimas:  python app.py   ->  http://127.0.0.1:5000
"""
import os
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for

from budget import db
from budget.classify import (
    ALL_CATEGORIES, EXPENSE, INCOME, KIND_LABELS, TRANSFER, TRANSFER_CATEGORY,
    import_transactions, reclassify_all,
)
from budget.parser import ParseError, parse_swedbank_csv

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("BUDGET_DB", BASE_DIR / "data" / "budget.db"))

app = Flask(__name__)
app.secret_key = os.environ.get("BUDGET_SECRET", "vietinis-naudojimas")


def get_db():
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = db.connect(DB_PATH)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.template_filter("eur")
def eur(value):
    return f"{value:,.2f} €".replace(",", " ").replace(".", ",")


@app.context_processor
def globals_for_templates():
    return {"KIND_LABELS": KIND_LABELS}


def _months(conn):
    return [r["m"] for r in conn.execute(
        "SELECT DISTINCT substr(date, 1, 7) AS m FROM transactions ORDER BY m DESC")]


def _all_categories(conn):
    used = {r["category"] for r in conn.execute("SELECT DISTINCT category FROM transactions")}
    ruled = {r["category"] for r in conn.execute("SELECT category FROM rules WHERE category IS NOT NULL")}
    return sorted(set(ALL_CATEGORIES) | used | ruled)


@app.route("/")
def dashboard():
    conn = get_db()
    months = _months(conn)
    month = request.args.get("month") or (months[0] if months else "")
    owner_expr = "COALESCE(NULLIF(a.owner, ''), NULLIF(a.label, ''), a.iban)"

    totals = conn.execute(
        "SELECT kind, SUM(amount) AS total FROM transactions "
        "WHERE substr(date, 1, 7) = ? GROUP BY kind", (month,),
    ).fetchall()
    sums = {r["kind"]: r["total"] or 0 for r in totals}
    income, expense = sums.get(INCOME, 0), -sums.get(EXPENSE, 0)

    by_category = conn.execute(
        "SELECT category, -SUM(amount) AS total, COUNT(*) AS n FROM transactions "
        "WHERE kind = ? AND substr(date, 1, 7) = ? GROUP BY category ORDER BY total DESC",
        (EXPENSE, month),
    ).fetchall()
    by_owner = conn.execute(
        f"SELECT {owner_expr} AS owner, "
        "SUM(CASE WHEN t.kind = ? THEN t.amount ELSE 0 END) AS income, "
        "-SUM(CASE WHEN t.kind = ? THEN t.amount ELSE 0 END) AS expense "
        "FROM transactions t JOIN accounts a ON a.iban = t.account "
        "WHERE substr(t.date, 1, 7) = ? GROUP BY owner ORDER BY owner",
        (INCOME, EXPENSE, month),
    ).fetchall()
    trend = conn.execute(
        "SELECT substr(date, 1, 7) AS m, "
        "SUM(CASE WHEN kind = ? THEN amount ELSE 0 END) AS income, "
        "-SUM(CASE WHEN kind = ? THEN amount ELSE 0 END) AS expense "
        "FROM transactions GROUP BY m ORDER BY m DESC LIMIT 12",
        (INCOME, EXPENSE),
    ).fetchall()
    transfers = conn.execute(
        "SELECT COUNT(*) AS n, SUM(ABS(amount)) AS total FROM transactions "
        "WHERE kind = ? AND substr(date, 1, 7) = ?", (TRANSFER, month),
    ).fetchone()

    return render_template(
        "dashboard.html", months=months, month=month, income=income, expense=expense,
        by_category=by_category, by_owner=by_owner, trend=list(reversed(trend)),
        transfers=transfers, max_category=max((r["total"] for r in by_category), default=0),
        max_trend=max((max(r["income"], r["expense"]) for r in trend), default=0),
    )


@app.route("/import", methods=["GET", "POST"])
def import_view():
    if request.method == "POST":
        conn = get_db()
        files = [f for f in request.files.getlist("files") if f.filename]
        if not files:
            flash("Pasirinkite bent vieną failą.", "error")
        for f in files:
            try:
                parsed = parse_swedbank_csv(f.read())
            except ParseError as exc:
                flash(f"{f.filename}: {exc}", "error")
                continue
            result = import_transactions(conn, parsed)
            flash(
                f"{f.filename}: pridėta naujų sandorių {result['added']}, "
                f"praleista jau esančių {result['skipped']}.", "ok",
            )
        unnamed = conn.execute("SELECT COUNT(*) FROM accounts WHERE owner = ''").fetchone()[0]
        if unnamed:
            flash("Yra sąskaitų be savininko – nurodykite jį nustatymuose.", "info")
        return redirect(url_for("import_view"))
    return render_template("import.html")


@app.route("/transactions")
def transactions():
    conn = get_db()
    filters = {k: request.args.get(k, "") for k in ("month", "account", "kind", "category", "q")}
    where, params = [], []
    if filters["month"]:
        where.append("substr(t.date, 1, 7) = ?")
        params.append(filters["month"])
    for key in ("account", "kind", "category"):
        if filters[key]:
            where.append(f"t.{key} = ?")
            params.append(filters[key])
    if filters["q"]:
        where.append("(t.counterparty LIKE ? OR t.description LIKE ?)")
        params += [f"%{filters['q']}%"] * 2
    sql = (
        "SELECT t.*, COALESCE(NULLIF(a.label, ''), a.iban) AS account_label, a.owner "
        "FROM transactions t JOIN accounts a ON a.iban = t.account "
        + ("WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY t.date DESC, t.id DESC LIMIT 1000"
    )
    rows = conn.execute(sql, params).fetchall()
    return render_template(
        "transactions.html", rows=rows, filters=filters, months=_months(conn),
        accounts=conn.execute("SELECT * FROM accounts ORDER BY owner, iban").fetchall(),
        categories=_all_categories(conn),
    )


@app.post("/transactions/<int:tx_id>")
def update_transaction(tx_id):
    conn = get_db()
    tx = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    if tx is None:
        return redirect(url_for("transactions"))
    kind = request.form.get("kind", tx["kind"])
    if kind not in KIND_LABELS:
        kind = tx["kind"]
    category = request.form.get("new_category", "").strip() or request.form.get("category", tx["category"])
    if kind == TRANSFER:
        category = TRANSFER_CATEGORY
    elif category == TRANSFER_CATEGORY:
        category = "Kita"

    if request.form.get("remember") and tx["counterparty"]:
        conn.execute("DELETE FROM rules WHERE pattern = ?", (tx["counterparty"],))
        conn.execute(
            "INSERT INTO rules(pattern, kind, category) VALUES (?, ?, ?)",
            (tx["counterparty"], kind, category),
        )
        conn.execute(
            "UPDATE transactions SET kind = ?, category = ?, locked = 0 WHERE id = ?",
            (kind, category, tx_id),
        )
        reclassify_all(conn)
        flash(f"Taisyklė „{tx['counterparty']}“ išsaugota ir pritaikyta.", "ok")
    else:
        conn.execute(
            "UPDATE transactions SET kind = ?, category = ?, locked = 1, pair_id = NULL, "
            "reason = 'pataisyta rankiniu būdu' WHERE id = ?",
            (kind, category, tx_id),
        )
    conn.commit()
    return redirect(request.form.get("back") or url_for("transactions"))


@app.post("/transactions/<int:tx_id>/unlock")
def unlock_transaction(tx_id):
    conn = get_db()
    conn.execute("UPDATE transactions SET locked = 0 WHERE id = ?", (tx_id,))
    reclassify_all(conn)
    conn.commit()
    return redirect(request.form.get("back") or url_for("transactions"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "household":
            db.set_setting(conn, "household_names", request.form.get("household_names", ""))
        elif action == "accounts":
            for acc in conn.execute("SELECT iban FROM accounts").fetchall():
                iban = acc["iban"]
                conn.execute(
                    "UPDATE accounts SET label = ?, owner = ?, kind = ? WHERE iban = ?",
                    (request.form.get(f"label_{iban}", "").strip(),
                     request.form.get(f"owner_{iban}", "").strip(),
                     request.form.get(f"kind_{iban}", "einamoji"), iban),
                )
        elif action == "add_rule":
            pattern = request.form.get("pattern", "").strip()
            kind = request.form.get("kind") or None
            category = request.form.get("category", "").strip() or None
            if pattern and (kind or category):
                conn.execute(
                    "INSERT INTO rules(pattern, kind, category) VALUES (?, ?, ?)",
                    (pattern, kind, category),
                )
        elif action == "delete_rule":
            conn.execute("DELETE FROM rules WHERE id = ?", (request.form.get("rule_id"),))
        reclassify_all(conn)
        conn.commit()
        flash("Išsaugota.", "ok")
        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        household=db.get_setting(conn, "household_names"),
        accounts=conn.execute(
            "SELECT a.*, COUNT(t.id) AS n FROM accounts a "
            "LEFT JOIN transactions t ON t.account = a.iban GROUP BY a.iban ORDER BY a.iban"
        ).fetchall(),
        rules=conn.execute("SELECT * FROM rules ORDER BY pattern").fetchall(),
        categories=_all_categories(conn),
    )


if __name__ == "__main__":
    # BUDGET_HOST=0.0.0.0 leidžia atidaryti programėlę telefonu per namų Wi-Fi.
    app.run(host=os.environ.get("BUDGET_HOST", "127.0.0.1"),
            debug=os.environ.get("FLASK_DEBUG") == "1")
