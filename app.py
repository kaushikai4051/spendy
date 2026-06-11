import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, add_expense as db_add_expense, get_expense, update_expense
from database.queries import get_summary_stats, get_recent_transactions, get_category_breakdown

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"

EXPENSE_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse_date(val: str | None) -> str | None:
    """Return val if it is a valid YYYY-MM-DD string, else None."""
    if not val:
        return None
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return val
    except ValueError:
        return None


def _fmt_date(s: str) -> str:
    """Format a YYYY-MM-DD string as '01 Jan 2025'."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return s


def _get_date_filter(args) -> tuple:
    """Parse and validate date range from request args. Returns (date_from, date_to, filter_label)."""
    date_from = _parse_date(args.get("from"))
    date_to = _parse_date(args.get("to"))
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
    filter_label = None
    if date_from or date_to:
        left = _fmt_date(date_from) if date_from else "All time"
        right = _fmt_date(date_to) if date_to else "present"
        filter_label = f"{left} – {right}"
    return date_from, date_to, filter_label


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([name, email, password, confirm_password]):
        return render_template("register.html", error="All fields are required.")
    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.")
    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    try:
        db = get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password))
        )
        db.commit()
        db.close()
    except sqlite3.IntegrityError:
        return render_template("register.html", error="An account with that email already exists.")

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not all([email, password]):
        return render_template("login.html", error="All fields are required.")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("dashboard.html", user_name=session["user_name"])


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    error = None

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip()
        cur_pw   = request.form.get("current_password", "")
        new_pw   = request.form.get("new_password", "")
        form_data = {"name": name, "email": email}

        if not name or not email:
            error = "Name and email are required."
        elif new_pw and not cur_pw:
            error = "Enter your current password to set a new one."
        elif new_pw and not check_password_hash(user["password_hash"], cur_pw):
            error = "Current password is incorrect."
        elif new_pw and len(new_pw) < 8:
            error = "New password must be at least 8 characters."
        else:
            try:
                if new_pw:
                    db.execute(
                        "UPDATE users SET name=?, email=?, password_hash=? WHERE id=?",
                        (name, email, generate_password_hash(new_pw), session["user_id"])
                    )
                else:
                    db.execute(
                        "UPDATE users SET name=?, email=? WHERE id=?",
                        (name, email, session["user_id"])
                    )
                db.commit()
                if name != session.get("user_name"):
                    session["user_name"] = name
                db.close()
                return redirect(url_for("profile"))
            except sqlite3.IntegrityError:
                error = "That email address is already in use."
    else:
        form_data = {"name": user["name"], "email": user["email"]}

    try:
        member_since = datetime.strptime(user["created_at"][:10], "%Y-%m-%d").strftime("%B %Y")
    except (ValueError, TypeError):
        member_since = "Unknown"

    db.close()

    date_from, date_to, filter_label = _get_date_filter(request.args)

    stats = get_summary_stats(session["user_id"], date_from=date_from, date_to=date_to)
    expense_count = stats["transaction_count"]
    expense_total = stats["total_spent"]

    recent_transactions = get_recent_transactions(session["user_id"], date_from=date_from, date_to=date_to)

    category_breakdown = get_category_breakdown(session["user_id"], date_from=date_from, date_to=date_to)

    return render_template(
        "profile.html",
        user=user,
        form_data=form_data,
        expense_count=expense_count,
        expense_total=expense_total,
        member_since=member_since,
        recent_transactions=recent_transactions,
        category_breakdown=category_breakdown,
        error=error,
        date_from=date_from,
        date_to=date_to,
        filter_label=filter_label,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=EXPENSE_CATEGORIES,
            form_data={"date": datetime.today().strftime("%Y-%m-%d"), "category": "Food"},
        )

    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date_raw = request.form.get("date", "").strip()
    desc_raw = request.form.get("description", "").strip()

    error = None
    amount = None
    date = None

    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError
    except ValueError:
        error = "Enter a valid amount greater than ₹0."

    if not error and category not in EXPENSE_CATEGORIES:
        error = "Select a valid category."

    if not error:
        date = _parse_date(date_raw)
        if not date:
            error = "Enter a valid date."

    if error:
        return render_template("add_expense.html", categories=EXPENSE_CATEGORIES,
                               form_data=request.form, error=error)

    description = desc_raw or None
    db_add_expense(session["user_id"], amount, category, date, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    expense = get_expense(id)
    if expense is None:
        return "Not found", 404
    if expense["user_id"] != session["user_id"]:
        return redirect(url_for("profile"))

    if request.method == "GET":
        form_data = {
            "amount": expense["amount"],
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        }
        return render_template("edit_expense.html",
                               categories=EXPENSE_CATEGORIES,
                               form_data=form_data,
                               expense_id=id)

    amount_raw = request.form.get("amount", "").strip()
    category   = request.form.get("category", "").strip()
    date_raw   = request.form.get("date", "").strip()
    desc_raw   = request.form.get("description", "").strip()

    error = None
    amount = None
    date = None

    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError
    except ValueError:
        error = "Enter a valid amount greater than ₹0."

    if not error and category not in EXPENSE_CATEGORIES:
        error = "Select a valid category."

    if not error:
        date = _parse_date(date_raw)
        if not date:
            error = "Enter a valid date."

    if error:
        return render_template("edit_expense.html",
                               categories=EXPENSE_CATEGORIES,
                               form_data=request.form,
                               expense_id=id,
                               error=error)

    description = desc_raw or None
    update_expense(id, session["user_id"], amount, category, date, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true", port=5001)
