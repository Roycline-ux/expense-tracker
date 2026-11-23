import os
import re
import sqlite3
from datetime import date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, g,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

# Set ALLOW_REGISTRATION to "0" on the server once your accounts exist
ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "1") == "1"

USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,30}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "expenses.db")


def parse_date(text):
    """Return a valid YYYY-MM-DD string that is not in the future, or None."""
    try:
        d = date.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    if d > date.today():
        return None
    return d.isoformat()


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                user_id INTEGER
            )
            """
        )
        # Upgrade an older expenses table that has no user_id column
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(expenses)")]
        if "user_id" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expenses_user ON expenses(user_id)"
        )


@app.before_request
def load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        with get_connection() as conn:
            g.user = conn.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if g.user is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register():
    if not ALLOW_REGISTRATION:
        flash("Registration is closed.")
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        error = None
        new_id = None
        if not USERNAME_RE.fullmatch(username):
            error = "Username must be 3-30 characters: letters, numbers, underscore."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."

        if error is None:
            try:
                with get_connection() as conn:
                    is_first = conn.execute(
                        "SELECT COUNT(*) FROM users"
                    ).fetchone()[0] == 0
                    cur = conn.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username.lower(), generate_password_hash(password)),
                    )
                    new_id = cur.lastrowid
                    if is_first:
                        # The first account inherits any older expenses
                        conn.execute(
                            "UPDATE expenses SET user_id = ? WHERE user_id IS NULL",
                            (new_id,),
                        )
            except sqlite3.IntegrityError:
                error = "That username is already taken."

        if error:
            flash(error)
        else:
            session.clear()
            session["user_id"] = new_id
            return redirect(url_for("index"))

    return render_template("register.html", allow_registration=ALLOW_REGISTRATION)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        with get_connection() as conn:
            user = conn.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
        flash("Wrong username or password.")

    return render_template("login.html", allow_registration=ALLOW_REGISTRATION)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    uid = g.user["id"]
    with get_connection() as conn:
        expenses = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC, id DESC",
            (uid,),
        ).fetchall()
        total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
            (uid,),
        ).fetchone()[0]
        categories = conn.execute(
            """
            SELECT category, SUM(amount) AS cat_total
            FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY cat_total DESC
            """,
            (uid,),
        ).fetchall()
        months = conn.execute(
            """
            SELECT substr(date, 1, 7) AS month, SUM(amount) AS month_total
            FROM expenses
            WHERE user_id = ?
            GROUP BY month
            ORDER BY month
            """,
            (uid,),
        ).fetchall()

    chart_data = {
        "cat_labels": [c["category"] for c in categories],
        "cat_values": [round(c["cat_total"], 2) for c in categories],
        "month_labels": [m["month"] for m in months],
        "month_values": [round(m["month_total"], 2) for m in months],
    }

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        categories=categories,
        chart_data=chart_data,
        today=date.today().isoformat(),
    )


@app.route("/add", methods=["POST"])
@login_required
def add():
    try:
        amount = float(request.form["amount"])
    except (ValueError, KeyError):
        flash("Please enter a valid amount.")
        return redirect(url_for("index"))

    if amount <= 0:
        flash("Amount must be greater than zero.")
        return redirect(url_for("index"))

    expense_date = parse_date(request.form.get("date", ""))
    if expense_date is None:
        flash("Please enter a valid date (not in the future).")
        return redirect(url_for("index"))

    category = request.form.get("category", "").strip().lower() or "other"
    description = request.form.get("description", "").strip()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO expenses (amount, category, description, date, user_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (amount, category, description, expense_date, g.user["id"]),
        )
    flash("Expense added!")
    return redirect(url_for("index"))


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit(expense_id):
    with get_connection() as conn:
        expense = conn.execute(
            "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, g.user["id"]),
        ).fetchone()

    if expense is None:
        flash("Expense not found.")
        return redirect(url_for("index"))

    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
        except (ValueError, KeyError):
            flash("Please enter a valid amount.")
            return redirect(url_for("edit", expense_id=expense_id))

        if amount <= 0:
            flash("Amount must be greater than zero.")
            return redirect(url_for("edit", expense_id=expense_id))

        expense_date = parse_date(request.form.get("date", ""))
        if expense_date is None:
            flash("Please enter a valid date (not in the future).")
            return redirect(url_for("edit", expense_id=expense_id))

        category = request.form.get("category", "").strip().lower() or "other"
        description = request.form.get("description", "").strip()

        with get_connection() as conn:
            conn.execute(
                "UPDATE expenses SET amount = ?, category = ?, description = ?, date = ? "
                "WHERE id = ? AND user_id = ?",
                (amount, category, description, expense_date, expense_id, g.user["id"]),
            )
        flash("Expense updated.")
        return redirect(url_for("index"))

    return render_template("edit.html", expense=expense, today=date.today().isoformat())


@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete(expense_id):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, g.user["id"]),
        )
    flash("Expense deleted.")
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)