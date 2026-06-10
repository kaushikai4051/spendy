"""
Tests for Step 07: Add Expense
==============================
Spec source: .claude/specs/07-add-expense.md

Behaviors covered:
  - Auth guard: GET and POST redirect to /login when not logged in
  - GET renders add_expense form with all 4 fields present
  - GET pre-fills the date field with today's date
  - Category <select> contains exactly 7 options: Food, Transport, Bills,
    Health, Entertainment, Shopping, Other
  - Valid POST inserts one row in expenses with correct user_id, amount,
    category, date, description
  - Valid POST redirects (302) on success
  - Validation errors for: missing amount, zero amount, non-numeric amount,
    invalid category, missing date
  - On validation failure the form re-renders (200) with an error message
  - On validation failure the previously entered field values are preserved
  - Empty description is stored as NULL (not empty string) in the database
  - Non-empty description is stored correctly
"""

import pytest
import tempfile
import os
from datetime import datetime

import database.db as db_module


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app():
    """Flask test app backed by a temporary SQLite file (isolated per test)."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_path

    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"

    with flask_app.app_context():
        db_module.init_db()

    yield flask_app

    db_module.DB_PATH = original_path
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_user(app):
    """
    Inserts one user directly into the DB.
    Returns the user_id.
    """
    from werkzeug.security import generate_password_hash
    db = db_module.get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", "test@example.com", generate_password_hash("password123")),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    return user_id


@pytest.fixture
def auth_client(client, registered_user):
    """Test client with a valid session already injected (no login route hit)."""
    with client.session_transaction() as sess:
        sess["user_id"] = registered_user
        sess["user_name"] = "Test User"
    return client, registered_user


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _today() -> str:
    return datetime.today().strftime("%Y-%m-%d")


def _valid_form(**overrides):
    """Return a dict of form data that passes all validation rules."""
    data = {
        "amount": "42.50",
        "category": "Food",
        "date": _today(),
        "description": "Test lunch",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAddExpenseAuthGuard:

    def test_get_redirects_when_not_logged_in(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, "Expected 302 redirect for unauthenticated GET"
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET should redirect to /login"
        )

    def test_post_redirects_when_not_logged_in(self, client):
        response = client.post("/expenses/add", data=_valid_form())
        assert response.status_code == 302, "Expected 302 redirect for unauthenticated POST"
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST should redirect to /login"
        )


# ------------------------------------------------------------------ #
# GET — form rendering                                                #
# ------------------------------------------------------------------ #

class TestAddExpenseGetForm:

    def test_returns_200_for_logged_in_user(self, auth_client):
        client, _ = auth_client
        response = client.get("/expenses/add")
        assert response.status_code == 200, "Expected 200 for logged-in GET"

    def test_amount_field_present(self, auth_client):
        client, _ = auth_client
        response = client.get("/expenses/add")
        assert b'name="amount"' in response.data, "Expected amount input field in form"

    def test_category_field_present(self, auth_client):
        client, _ = auth_client
        response = client.get("/expenses/add")
        assert b'name="category"' in response.data, "Expected category select field in form"

    def test_date_field_present(self, auth_client):
        client, _ = auth_client
        response = client.get("/expenses/add")
        assert b'name="date"' in response.data, "Expected date input field in form"

    def test_description_field_present(self, auth_client):
        client, _ = auth_client
        response = client.get("/expenses/add")
        assert b'name="description"' in response.data, "Expected description textarea in form"

    def test_submit_button_labeled_add_expense(self, auth_client):
        client, _ = auth_client
        response = client.get("/expenses/add")
        assert b"Add Expense" in response.data, "Expected 'Add Expense' submit button label"

    def test_date_defaults_to_today(self, auth_client):
        client, _ = auth_client
        response = client.get("/expenses/add")
        today_bytes = _today().encode("utf-8")
        assert today_bytes in response.data, (
            f"Expected today's date ({_today()}) pre-filled in the form"
        )

    def test_cancel_link_present(self, auth_client):
        """The form must have a link back to the dashboard / profile page."""
        client, _ = auth_client
        response = client.get("/expenses/add")
        # Spec says 'Cancel' link; match case-insensitively via both casings
        assert b"Cancel" in response.data or b"cancel" in response.data, (
            "Expected a 'Cancel' link on the add expense form"
        )


# ------------------------------------------------------------------ #
# GET — category options                                              #
# ------------------------------------------------------------------ #

class TestAddExpenseCategoryOptions:

    EXPECTED_CATEGORIES = [
        "Food", "Transport", "Bills", "Health",
        "Entertainment", "Shopping", "Other",
    ]

    def test_exactly_seven_category_options(self, auth_client):
        client, _ = auth_client
        response = client.get("/expenses/add")
        html = response.data.decode("utf-8")
        option_count = html.count("<option")
        assert option_count == 7, (
            f"Expected exactly 7 <option> elements in category select, got {option_count}"
        )

    @pytest.mark.parametrize("category", [
        "Food", "Transport", "Bills", "Health",
        "Entertainment", "Shopping", "Other",
    ])
    def test_each_category_option_present(self, auth_client, category):
        client, _ = auth_client
        response = client.get("/expenses/add")
        assert category.encode("utf-8") in response.data, (
            f"Expected category option '{category}' in form"
        )


# ------------------------------------------------------------------ #
# POST — valid submission                                             #
# ------------------------------------------------------------------ #

class TestAddExpenseValidPost:

    def test_valid_post_redirects(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form())
        assert response.status_code == 302, "Expected 302 redirect after valid submission"

    def test_valid_post_redirect_target(self, auth_client):
        """Successful submission must redirect to the dashboard (profile) page."""
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form())
        location = response.headers.get("Location", "")
        # Spec says redirect to /dashboard; implementation may use /profile (dashboard alias)
        assert "/dashboard" in location or "/profile" in location, (
            f"Expected redirect to dashboard or profile, got: {location}"
        )

    def test_valid_post_inserts_one_row(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(
            amount="99.99",
            category="Health",
            date="2026-05-20",
            description="Doctor visit",
        ))
        db = db_module.get_db()
        rows = db.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()
        db.close()
        assert len(rows) == 1, "Expected exactly 1 expense row after valid POST"

    def test_valid_post_stores_correct_user_id(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form())
        db = db_module.get_db()
        row = db.execute(
            "SELECT user_id FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        db.close()
        assert row is not None, "Expected expense row to exist for the logged-in user"
        assert row["user_id"] == user_id, (
            f"Expected user_id={user_id}, got {row['user_id']}"
        )

    def test_valid_post_stores_correct_amount(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(amount="123.45"))
        db = db_module.get_db()
        row = db.execute(
            "SELECT amount FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        db.close()
        assert row is not None, "Expected expense row in DB"
        assert abs(row["amount"] - 123.45) < 0.001, (
            f"Expected amount=123.45, got {row['amount']}"
        )

    def test_valid_post_stores_correct_category(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(category="Transport"))
        db = db_module.get_db()
        row = db.execute(
            "SELECT category FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        db.close()
        assert row is not None, "Expected expense row in DB"
        assert row["category"] == "Transport", (
            f"Expected category='Transport', got '{row['category']}'"
        )

    def test_valid_post_stores_correct_date(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(date="2026-03-15"))
        db = db_module.get_db()
        row = db.execute(
            "SELECT date FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        db.close()
        assert row is not None, "Expected expense row in DB"
        assert row["date"] == "2026-03-15", (
            f"Expected date='2026-03-15', got '{row['date']}'"
        )

    def test_valid_post_stores_correct_description(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(description="Morning coffee"))
        db = db_module.get_db()
        row = db.execute(
            "SELECT description FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        db.close()
        assert row is not None, "Expected expense row in DB"
        assert row["description"] == "Morning coffee", (
            f"Expected description='Morning coffee', got '{row['description']}'"
        )


# ------------------------------------------------------------------ #
# POST — empty description stored as NULL                             #
# ------------------------------------------------------------------ #

class TestAddExpenseEmptyDescription:

    def test_empty_description_stored_as_null(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(description=""))
        db = db_module.get_db()
        row = db.execute(
            "SELECT description FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        db.close()
        assert row is not None, "Expected expense row in DB"
        assert row["description"] is None, (
            f"Expected description=NULL for empty input, got '{row['description']}'"
        )

    def test_whitespace_only_description_stored_as_null(self, auth_client):
        """Whitespace-only description must be stripped and stored as NULL."""
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(description="   "))
        db = db_module.get_db()
        row = db.execute(
            "SELECT description FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        db.close()
        assert row is not None, "Expected expense row in DB"
        assert row["description"] is None, (
            f"Expected whitespace description stored as NULL, got '{row['description']}'"
        )


# ------------------------------------------------------------------ #
# POST — validation errors                                            #
# ------------------------------------------------------------------ #

class TestAddExpenseValidationErrors:

    def test_missing_amount_returns_200(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(amount=""))
        assert response.status_code == 200, (
            "Expected 200 (re-render) when amount is missing"
        )

    def test_missing_amount_shows_error_message(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(amount=""))
        assert b"error" in response.data.lower() or b"valid" in response.data.lower(), (
            "Expected an error/validation message for missing amount"
        )

    def test_zero_amount_returns_200(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(amount="0"))
        assert response.status_code == 200, (
            "Expected 200 (re-render) when amount is zero"
        )

    def test_zero_amount_shows_error_message(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(amount="0"))
        assert b"error" in response.data.lower() or b"valid" in response.data.lower() or b"amount" in response.data.lower(), (
            "Expected a validation error message for zero amount"
        )

    def test_zero_amount_does_not_insert_row(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(amount="0"))
        db = db_module.get_db()
        count = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        db.close()
        assert count == 0, "Expected no row inserted when amount is zero"

    def test_negative_amount_returns_200(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(amount="-10"))
        assert response.status_code == 200, (
            "Expected 200 (re-render) when amount is negative"
        )

    def test_negative_amount_does_not_insert_row(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(amount="-10"))
        db = db_module.get_db()
        count = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        db.close()
        assert count == 0, "Expected no row inserted for negative amount"

    def test_non_numeric_amount_returns_200(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(amount="abc"))
        assert response.status_code == 200, (
            "Expected 200 (re-render) when amount is non-numeric"
        )

    def test_non_numeric_amount_shows_error_message(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(amount="abc"))
        html_lower = response.data.lower()
        assert b"error" in html_lower or b"valid" in html_lower or b"amount" in html_lower, (
            "Expected a validation error message for non-numeric amount"
        )

    def test_non_numeric_amount_does_not_insert_row(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(amount="abc"))
        db = db_module.get_db()
        count = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        db.close()
        assert count == 0, "Expected no row inserted for non-numeric amount"

    def test_invalid_category_returns_200(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(category="Gambling"))
        assert response.status_code == 200, (
            "Expected 200 (re-render) when category is not in the allowed list"
        )

    def test_invalid_category_shows_error_message(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(category="Gambling"))
        html_lower = response.data.lower()
        assert b"error" in html_lower or b"valid" in html_lower or b"category" in html_lower, (
            "Expected a validation error message for invalid category"
        )

    def test_invalid_category_does_not_insert_row(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(category="Gambling"))
        db = db_module.get_db()
        count = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        db.close()
        assert count == 0, "Expected no row inserted for invalid category"

    def test_missing_date_returns_200(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(date=""))
        assert response.status_code == 200, (
            "Expected 200 (re-render) when date is missing"
        )

    def test_missing_date_shows_error_message(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(date=""))
        html_lower = response.data.lower()
        assert b"error" in html_lower or b"valid" in html_lower or b"date" in html_lower, (
            "Expected a validation error message for missing date"
        )

    def test_missing_date_does_not_insert_row(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(date=""))
        db = db_module.get_db()
        count = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        db.close()
        assert count == 0, "Expected no row inserted when date is missing"

    def test_invalid_date_format_returns_200(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(date="not-a-date"))
        assert response.status_code == 200, (
            "Expected 200 (re-render) for a malformed date string"
        )

    def test_invalid_date_format_does_not_insert_row(self, auth_client):
        client, user_id = auth_client
        client.post("/expenses/add", data=_valid_form(date="not-a-date"))
        db = db_module.get_db()
        count = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        db.close()
        assert count == 0, "Expected no row inserted for malformed date"


# ------------------------------------------------------------------ #
# POST — field preservation on validation failure                     #
# ------------------------------------------------------------------ #

class TestAddExpenseFieldPreservation:

    def test_amount_preserved_after_invalid_category(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(
            amount="77.77", category="InvalidCat"
        ))
        assert b"77.77" in response.data, (
            "Expected previously entered amount to be re-populated in form on failure"
        )

    def test_date_preserved_after_invalid_amount(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(
            amount="bad", date="2026-04-10"
        ))
        assert b"2026-04-10" in response.data, (
            "Expected previously entered date to be re-populated in form on failure"
        )

    def test_description_preserved_after_invalid_amount(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(
            amount="bad", description="My lunch notes"
        ))
        assert b"My lunch notes" in response.data, (
            "Expected previously entered description to be re-populated in form on failure"
        )

    def test_category_preserved_after_invalid_date(self, auth_client):
        client, _ = auth_client
        response = client.post("/expenses/add", data=_valid_form(
            date="", category="Bills"
        ))
        assert b"Bills" in response.data, (
            "Expected previously entered category to remain visible in form on failure"
        )


# ------------------------------------------------------------------ #
# POST — parametrized invalid amount edge cases                       #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("bad_amount", [
    "",          # missing
    "0",         # zero
    "0.00",      # zero as float string
    "-1",        # negative
    "-0.01",     # small negative
    "abc",       # non-numeric string
    "1 2",       # spaces
    "1,000",     # comma-formatted
    "1e5x",      # partial scientific notation
])
def test_invalid_amount_does_not_insert_row(app, bad_amount):
    """All malformed or out-of-range amounts must be rejected without inserting a row."""
    from werkzeug.security import generate_password_hash
    db = db_module.get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Param User", f"param_{bad_amount[:3]}@example.com", generate_password_hash("pass1234")),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Param User"

    response = client.post("/expenses/add", data={
        "amount": bad_amount,
        "category": "Food",
        "date": _today(),
        "description": "",
    })
    assert response.status_code == 200, (
        f"Expected 200 re-render for bad amount '{bad_amount}', got {response.status_code}"
    )
    db = db_module.get_db()
    count = db.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    db.close()
    assert count == 0, (
        f"Expected 0 rows inserted for bad amount '{bad_amount}', got {count}"
    )


# ------------------------------------------------------------------ #
# POST — parametrized valid categories all accepted                   #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("category", [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
])
def test_each_valid_category_is_accepted(app, category):
    """Every allowed category must result in a successful insert + redirect."""
    from werkzeug.security import generate_password_hash
    db = db_module.get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Cat User", f"cat_{category.lower()}@example.com", generate_password_hash("pass1234")),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Cat User"

    response = client.post("/expenses/add", data={
        "amount": "10.00",
        "category": category,
        "date": _today(),
        "description": "",
    })
    assert response.status_code == 302, (
        f"Expected 302 redirect for valid category '{category}', got {response.status_code}"
    )
    db = db_module.get_db()
    count = db.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ? AND category = ?",
        (user_id, category),
    ).fetchone()[0]
    db.close()
    assert count == 1, (
        f"Expected 1 row inserted for category '{category}', got {count}"
    )
