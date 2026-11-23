import csv
import io
import os
import re
import sqlite3
from datetime import date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, g, Response,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

# Set ALLOW_REGISTRATION to "0" on the server once your accounts exist
ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "1") == "1"

USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,30}")
MONTH_RE = re.compile(r"\d{4}-\d{2}")

WARN_AT = 80  # percent of budget that triggers a warning

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


def parse_start_date(text):
    """Like parse_date, but a future start date is allowed."""
    try:
        d = date.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    if d.year < 2000:
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
        user_columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
        if "pw_version" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN pw_version INTEGER NOT NULL DEFAULT 0")

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
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(expenses)")]
        if "user_id" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expenses_user ON expenses(user_id)"
        )
        # category '' means the overall monthly budget
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                amount REAL NOT NULL,
                UNIQUE (user_id, category)
            )
            """
        )
        # last_month remembers the newest month already generated ('YYYY-MM')
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recurring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                day INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                last_month TEXT NOT NULL DEFAULT ''
            )
            """
        )


@app.before_request
def load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, pw_version FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        # A changed password bumps pw_version and invalidates older sessions
        if row is not None and row["pw_version"] == session.get("pw_version", 0):
            g.user = row
        else:
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
            session["pw_version"] = 0
            return redirect(url_for("index"))

    return render_template("register.html", allow_registration=ALLOW_REGISTRATION)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        with get_connection() as conn:
            user = conn.execute(
                "SELECT id, password_hash, pw_version FROM users WHERE username = ?",
                (username,),
            ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["pw_version"] = user["pw_version"]
            return redirect(url_for("index"))
        flash("Wrong username or password.")

    return render_template("login.html", allow_registration=ALLOW_REGISTRATION)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current", "")
        new = request.form.get("new", "")
        confirm = request.form.get("confirm", "")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT password_hash, pw_version FROM users WHERE id = ?",
                (g.user["id"],),
            ).fetchone()

        error = None
        if not check_password_hash(row["password_hash"], current):
            error = "Your current password is incorrect."
        elif len(new) < 8:
            error = "New password must be at least 8 characters."
        elif new != confirm:
            error = "New passwords do not match."
        elif check_password_hash(row["password_hash"], new):
            error = "New password must be different from the current one."

        if error:
            flash(error)
            return redirect(url_for("change_password"))

        new_version = row["pw_version"] + 1
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, pw_version = ? WHERE id = ?",
                (generate_password_hash(new), new_version, g.user["id"]),
            )

        # Keep this device signed in; every other device is signed out
        session["pw_version"] = new_version
        flash("Password changed. Other devices have been signed out.")
        return redirect(url_for("index"))

    return render_template("change_password.html")


def get_filters():
    """Read the month, category and search text from the URL."""
    month = request.args.get("month", "")
    if not MONTH_RE.fullmatch(month):
        month = ""
    category = request.args.get("category", "").strip().lower()
    q = request.args.get("q", "").strip()[:100]
    return month, category, q


def build_where(uid, month, category, q):
    """Build a safe WHERE clause (values are passed as parameters)."""
    where = "user_id = ?"
    params = [uid]
    if month:
        where += " AND substr(date, 1, 7) = ?"
        params.append(month)
    if category:
        where += " AND category = ?"
        params.append(category)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where += " AND description LIKE ? ESCAPE '\\'"
        params.append(f"%{escaped}%")
    return where, params


def apply_recurring(conn, uid):
    """Create any recurring expenses that are due and not yet created."""
    today = date.today()
    rules = conn.execute(
        "SELECT * FROM recurring WHERE user_id = ?", (uid,)
    ).fetchall()

    for r in rules:
        start = date.fromisoformat(r["start_date"])
        last = r["last_month"]
        y, m = start.year, start.month

        while True:
            due = date(y, m, r["day"])
            if due > today:
                break
            ym = f"{y:04d}-{m:02d}"
            if due >= start and ym > last:
                conn.execute(
                    "INSERT INTO expenses (amount, category, description, date, user_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (r["amount"], r["category"], r["description"], due.isoformat(), uid),
                )
                last = ym
            m += 1
            if m > 12:
                m = 1
                y += 1

        if last != r["last_month"]:
            conn.execute(
                "UPDATE recurring SET last_month = ? WHERE id = ?", (last, r["id"])
            )


def build_budget_status(conn, uid, this_month):
    """Compare this month's spending with each budget."""
    rows = conn.execute(
        """
        SELECT category, SUM(amount) AS spent
        FROM expenses
        WHERE user_id = ? AND substr(date, 1, 7) = ?
        GROUP BY category
        """,
        (uid, this_month),
    ).fetchall()
    spent_by_cat = {r["category"]: r["spent"] for r in rows}
    overall_spent = sum(spent_by_cat.values())

    budgets = conn.execute(
        "SELECT * FROM budgets WHERE user_id = ? "
        "ORDER BY (category = '') DESC, category",
        (uid,),
    ).fetchall()

    status = []
    for b in budgets:
        spent = overall_spent if b["category"] == "" else spent_by_cat.get(b["category"], 0)
        limit = b["amount"]
        pct = spent / limit * 100 if limit else 0
        if pct > 100:
            level = "over"
        elif pct >= WARN_AT:
            level = "warn"
        else:
            level = "ok"
        status.append({
            "id": b["id"],
            "label": b["category"] or "Overall",
            "spent": spent,
            "limit": limit,
            "pct": pct,
            "bar": min(pct, 100),
            "level": level,
        })
    return status


@app.route("/")
@login_required
def index():
    uid = g.user["id"]
    today = date.today().isoformat()
    this_month = today[:7]

    month, category, q = get_filters()
    where, params = build_where(uid, month, category, q)
    # The monthly chart ignores the month filter but keeps category and search
    chart_where, chart_params = build_where(uid, "", category, q)

    with get_connection() as conn:
        apply_recurring(conn, uid)

        expenses = conn.execute(
            f"SELECT * FROM expenses WHERE {where} ORDER BY date DESC, id DESC",
            params,
        ).fetchall()
        total = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE {where}",
            params,
        ).fetchone()[0]
        categories = conn.execute(
            f"""
            SELECT category, SUM(amount) AS cat_total
            FROM expenses
            WHERE {where}
            GROUP BY category
            ORDER BY cat_total DESC
            """,
            params,
        ).fetchall()
        months = conn.execute(
            f"""
            SELECT substr(date, 1, 7) AS month, SUM(amount) AS month_total
            FROM expenses
            WHERE {chart_where}
            GROUP BY month
            ORDER BY month
            """,
            chart_params,
        ).fetchall()
        month_options = [
            r["m"] for r in conn.execute(
                "SELECT DISTINCT substr(date, 1, 7) AS m FROM expenses "
                "WHERE user_id = ? ORDER BY m DESC",
                (uid,),
            )
        ]
        category_options = [
            r["category"] for r in conn.execute(
                "SELECT DISTINCT category FROM expenses "
                "WHERE user_id = ? ORDER BY category",
                (uid,),
            )
        ]
        budget_status = build_budget_status(conn, uid, this_month)
        recurring = conn.execute(
            "SELECT * FROM recurring WHERE user_id = ? ORDER BY day, id",
            (uid,),
        ).fetchall()

    alerts = []
    for b in budget_status:
        if b["level"] == "over":
            alerts.append({
                "level": "over",
                "text": f"Over budget: {b['label']} is at {b['spent']:,.2f} of {b['limit']:,.2f} this month.",
            })
        elif b["level"] == "warn":
            alerts.append({
                "level": "warn",
                "text": f"Close to budget: {b['label']} has used {b['pct']:.0f}% ({b['spent']:,.2f} of {b['limit']:,.2f}).",
            })

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
        today=today,
        this_month=this_month,
        month=month,
        category=category,
        q=q,
        month_options=month_options,
        category_options=category_options,
        budget_status=budget_status,
        alerts=alerts,
        warn_at=WARN_AT,
        recurring=recurring,
    )


def csv_safe(value):
    """Stop spreadsheet apps from running text that starts like a formula."""
    text = "" if value is None else str(value)
    if text and text[0] in "=+-@\t\r":
        return "'" + text
    return text


@app.route("/export")
@login_required
def export_csv():
    month, category, q = get_filters()
    where, params = build_where(g.user["id"], month, category, q)

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT date, category, amount, description FROM expenses "
            f"WHERE {where} ORDER BY date DESC, id DESC",
            params,
        ).fetchall()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Category", "Amount", "Description"])
    for r in rows:
        writer.writerow([
            r["date"],
            csv_safe(r["category"]),
            f"{r['amount']:.2f}",
            csv_safe(r["description"]),
        ])

    filename = f"expenses-{date.today().isoformat()}.csv"
    # The leading BOM lets Excel read the file as UTF-8
    return Response(
        "\ufeff" + out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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


@app.route("/recurring", methods=["POST"])
@login_required
def add_recurring():
    try:
        amount = float(request.form["amount"])
    except (ValueError, KeyError):
        flash("Please enter a valid amount.")
        return redirect(url_for("index"))

    if amount <= 0:
        flash("Amount must be greater than zero.")
        return redirect(url_for("index"))

    try:
        day = int(request.form["day"])
    except (ValueError, KeyError):
        flash("Please enter a day of the month from 1 to 28.")
        return redirect(url_for("index"))

    if day < 1 or day > 28:
        flash("Day must be between 1 and 28.")
        return redirect(url_for("index"))

    start = parse_start_date(request.form.get("start", ""))
    if start is None:
        flash("Please enter a valid start date.")
        return redirect(url_for("index"))

    category = request.form.get("category", "").strip().lower() or "other"
    description = request.form.get("description", "").strip()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO recurring (user_id, amount, category, description, day, start_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (g.user["id"], amount, category, description, day, start),
        )
    flash("Recurring expense saved. Due expenses are added automatically.")
    return redirect(url_for("index"))


@app.route("/recurring/delete/<int:recurring_id>", methods=["POST"])
@login_required
def delete_recurring(recurring_id):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM recurring WHERE id = ? AND user_id = ?",
            (recurring_id, g.user["id"]),
        )
    flash("Recurring expense stopped. Past expenses were kept.")
    return redirect(url_for("index"))


@app.route("/budget", methods=["POST"])
@login_required
def set_budget():
    category = request.form.get("category", "").strip().lower()
    try:
        amount = float(request.form["amount"])
    except (ValueError, KeyError):
        flash("Please enter a valid budget amount.")
        return redirect(url_for("index"))

    if amount <= 0:
        flash("Budget must be greater than zero.")
        return redirect(url_for("index"))

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO budgets (user_id, category, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, category) DO UPDATE SET amount = excluded.amount
            """,
            (g.user["id"], category, amount),
        )
    flash("Budget saved.")
    return redirect(url_for("index"))


@app.route("/budget/delete/<int:budget_id>", methods=["POST"])
@login_required
def delete_budget(budget_id):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM budgets WHERE id = ? AND user_id = ?",
            (budget_id, g.user["id"]),
        )
    flash("Budget removed.")
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)