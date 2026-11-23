import sqlite3
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "change-this-to-something-random"

DB_FILE = "expenses.db"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL
            )
            """
        )


@app.route("/")
def index():
    with get_connection() as conn:
        expenses = conn.execute(
            "SELECT * FROM expenses ORDER BY date DESC, id DESC"
        ).fetchall()
        total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses"
        ).fetchone()[0]
        categories = conn.execute(
            """
            SELECT category, SUM(amount) AS cat_total
            FROM expenses
            GROUP BY category
            ORDER BY cat_total DESC
            """
        ).fetchall()

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        categories=categories,
    )


@app.route("/add", methods=["POST"])
def add():
    try:
        amount = float(request.form["amount"])
    except (ValueError, KeyError):
        flash("Please enter a valid amount.")
        return redirect(url_for("index"))

    if amount <= 0:
        flash("Amount must be greater than zero.")
        return redirect(url_for("index"))

    category = request.form.get("category", "").strip().lower() or "other"
    description = request.form.get("description", "").strip()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO expenses (amount, category, description, date) VALUES (?, ?, ?, ?)",
            (amount, category, description, str(date.today())),
        )
    flash("Expense added!")
    return redirect(url_for("index"))


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    flash("Expense deleted.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)