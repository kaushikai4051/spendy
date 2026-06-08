import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db
from database.queries import get_summary_stats, get_recent_transactions, get_category_breakdown

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"

with app.app_context():
    init_db()
    seed_db()


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

    from datetime import datetime

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

    # ── Sub-agent-2: Summary Stats ──────────────────────────────────
    stats         = get_summary_stats(session["user_id"])
    expense_count = stats["transaction_count"]
    expense_total = stats["total_spent"]
    # END SUB-AGENT-2

    # ── Sub-agent-1: Transaction History ───────────────────────────
    recent_transactions = get_recent_transactions(session["user_id"])
    # END SUB-AGENT-1

    # ── Sub-agent-3: Category Breakdown ────────────────────────────
    category_breakdown = get_category_breakdown(session["user_id"])
    # END SUB-AGENT-3

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
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
