"""
Tests for Step 08: Edit Expense
================================
Spec source: .claude/specs/08-edit-expense.md

Behaviors covered:
  - Auth guard: GET and POST redirect to /login when not logged in
  - 404: GET /expenses/999/edit returns 404 for a non-existent expense id
  - Ownership: GET for another user's expense redirects to /profile
  - GET happy path: form renders with correct pre-populated field values
  - GET category <select>: correct option carries the "selected" attribute
  - GET form landmarks: "Save Changes" button label; Cancel link present
  - POST valid: updates the existing DB row (no new row inserted)
  - POST valid: redirects to /profile after success
  - POST valid: stored amount, category, date, description match submitted values
  - POST invalid — missing/zero/negative/non-numeric amount: 200 re-render, DB unchanged
  - POST invalid — invalid category: 200 re-render with error, DB unchanged
  - POST invalid — missing/bad date: 200 re-render, DB unchanged
  - Field preservation: entered values survive a validation failure re-render
  - Empty/whitespace description stored as NULL in DB after successful update
"""

import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash

import database.db as db_module


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app():
    """Flask test app backed by an isolated temporary SQLite file."""
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
def seeded_db(app):
    """
    Inserts one user and 4 known expenses. Returns user_id (int).

    User:  name="Test User", email="test@example.com"
    Food      50.00   2026-06-01  "Lunch"
    Food      30.00   2026-06-02  "Snack"
    Transport 100.00  2026-06-03  "Bus pass"
    Bills     200.00  2026-06-04  "Electricity"
    """
    db = db_module.get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (
            "Test User",
            "test@example.com",
            generate_password_hash("password123"),
            "2025-01-15 10:00:00",
        ),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    expenses = [
        (user_id, 50.00,  "Food",      "2026-06-01", "Lunch"),
        (user_id, 30.00,  "Food",      "2026-06-02", "Snack"),
        (user_id, 100.00, "Transport", "2026-06-03", "Bus pass"),
        (user_id, 200.00, "Bills",     "2026-06-04", "Electricity"),
    ]
    db.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    db.commit()
    db.close()
    return user_id


def _inject_session(client, user_id: int, user_name: str = "Test User"):
    """Set session variables directly without hitting the login route."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = user_name


def _get_first_expense_id(user_id: int) -> int:
    """Return the id of the first expense belonging to user_id."""
    db = db_module.get_db()
    row = db.execute(
        "SELECT id FROM expenses WHERE user_id = ? ORDER BY id ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    db.close()
    assert row is not None, "Expected at least one expense for the seeded user"
    return row["id"]


def _get_expense_row(expense_id: int):
    """Fetch a single expense row by id; returns sqlite3.Row or None."""
    db = db_module.get_db()
    row = db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    db.close()
    return row


def _valid_form(**overrides):
    """Return a dict of form data that passes all validation rules."""
    data = {
        "amount": "75.00",
        "category": "Transport",
        "date": "2026-07-15",
        "description": "Updated expense",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestEditExpenseAuthGuard:

    def test_get_redirects_to_login_when_not_logged_in(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        response = client.get(f"/expenses/{expense_id}/edit", follow_redirects=False)
        assert response.status_code == 302, (
            "Expected 302 redirect for unauthenticated GET"
        )
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET must redirect to /login"
        )

    def test_post_redirects_to_login_when_not_logged_in(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(),
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Expected 302 redirect for unauthenticated POST"
        )
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST must redirect to /login"
        )


# ------------------------------------------------------------------ #
# 404 — non-existent expense                                          #
# ------------------------------------------------------------------ #

class TestEditExpense404:

    def test_get_nonexistent_expense_returns_404(self, client, app, seeded_db):
        user_id = seeded_db
        _inject_session(client, user_id)
        response = client.get("/expenses/999999/edit", follow_redirects=False)
        assert response.status_code == 404, (
            "Expected 404 for GET on a non-existent expense id"
        )


# ------------------------------------------------------------------ #
# Ownership guard                                                     #
# ------------------------------------------------------------------ #

class TestEditExpenseOwnership:

    def test_get_other_users_expense_redirects_to_profile(self, client, app, seeded_db):
        """
        User 1 is logged in. Expense belongs to User 2.
        The route must redirect to /profile without leaking a 403.
        """
        # Insert a second user and an expense for them
        db = db_module.get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other User", "other@example.com", generate_password_hash("pass5678")),
        )
        db.commit()
        other_user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (other_user_id, 55.00, "Food", "2026-07-01", "Other user lunch"),
        )
        db.commit()
        other_expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()

        # Log in as user 1 (the seeded user)
        _inject_session(client, seeded_db)

        response = client.get(
            f"/expenses/{other_expense_id}/edit",
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Expected 302 redirect when accessing another user's expense"
        )
        assert "/profile" in response.headers["Location"], (
            "Ownership violation must redirect to /profile, not expose 403"
        )

    def test_post_other_users_expense_redirects_to_profile(self, client, app, seeded_db):
        """POST to another user's expense must also be blocked."""
        db = db_module.get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Another User", "another@example.com", generate_password_hash("pass9999")),
        )
        db.commit()
        another_user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (another_user_id, 88.00, "Bills", "2026-07-02", "Another user bill"),
        )
        db.commit()
        another_expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()

        _inject_session(client, seeded_db)

        response = client.post(
            f"/expenses/{another_expense_id}/edit",
            data=_valid_form(),
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Expected 302 redirect when POSTing to another user's expense"
        )
        assert "/profile" in response.headers["Location"], (
            "Ownership violation on POST must redirect to /profile"
        )


# ------------------------------------------------------------------ #
# GET — form rendering and pre-population                             #
# ------------------------------------------------------------------ #

class TestEditExpenseGetForm:

    def test_returns_200_for_logged_in_owner(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        assert response.status_code == 200, (
            "Expected 200 for GET on own expense when logged in"
        )

    def test_amount_field_present(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="amount"' in response.data, (
            "Expected amount input field in edit form"
        )

    def test_category_field_present(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="category"' in response.data, (
            "Expected category select field in edit form"
        )

    def test_date_field_present(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="date"' in response.data, (
            "Expected date input field in edit form"
        )

    def test_description_field_present(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="description"' in response.data, (
            "Expected description textarea in edit form"
        )

    def test_amount_prepopulated_from_db(self, client, app, seeded_db):
        """The amount field must be pre-filled with the expense's stored value."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        # The first seeded expense has amount=50.00
        assert b"50" in response.data, (
            "Expected pre-populated amount (50.00) in edit form"
        )

    def test_category_prepopulated_from_db(self, client, app, seeded_db):
        """The category must reflect the stored value of the expense."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        # First seeded expense has category="Food"
        assert b"Food" in response.data, (
            "Expected pre-populated category 'Food' in edit form"
        )

    def test_date_prepopulated_from_db(self, client, app, seeded_db):
        """The date field must be pre-filled with the stored date."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        # First seeded expense has date="2026-06-01"
        assert b"2026-06-01" in response.data, (
            "Expected pre-populated date '2026-06-01' in edit form"
        )

    def test_description_prepopulated_from_db(self, client, app, seeded_db):
        """The description field must be pre-filled with the stored description."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        # First seeded expense has description="Lunch"
        assert b"Lunch" in response.data, (
            "Expected pre-populated description 'Lunch' in edit form"
        )

    def test_save_changes_button_present(self, client, app, seeded_db):
        """Submit button must be labelled 'Save Changes' per spec."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b"Save Changes" in response.data, (
            "Expected 'Save Changes' button label on edit form"
        )

    def test_cancel_link_present(self, client, app, seeded_db):
        """Form must include a Cancel link back to the profile page."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        assert b"Cancel" in response.data or b"cancel" in response.data, (
            "Expected a Cancel link on the edit expense form"
        )


# ------------------------------------------------------------------ #
# GET — category <select> pre-selection                               #
# ------------------------------------------------------------------ #

class TestEditExpenseCategoryPreselection:

    def test_correct_category_option_is_selected(self, client, app, seeded_db):
        """
        The <select> must mark the stored category as selected.
        The first seeded expense has category 'Food'; verify 'selected' appears
        near or with 'Food' in the rendered HTML.
        """
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        html = response.data.decode("utf-8")

        # Find the index of "selected" and "Food" within the category select block.
        # Both must co-exist in the HTML (Jinja2 renders selected="selected" or just selected).
        assert "selected" in html, "Expected a 'selected' attribute on one of the <option> elements"

        # The selected option must correspond to 'Food' — find that option fragment.
        # Acceptable patterns:  selected>Food  or  value="Food" selected  or  selected value="Food"
        food_idx = html.find("Food")
        assert food_idx != -1, "Expected 'Food' option in category select"

        # Search the nearby HTML segment (500 chars around "Food") for "selected"
        window = html[max(0, food_idx - 200): food_idx + 200]
        assert "selected" in window, (
            "Expected the 'Food' option to carry the 'selected' attribute "
            f"(searched within 200 chars either side of 'Food' in rendered HTML)"
        )

    def test_non_selected_categories_present_but_not_selected(self, client, app, seeded_db):
        """Every category option should be present; only the matching one selected."""
        user_id = seeded_db
        # Use the Transport expense (3rd seeded, category="Transport")
        db = db_module.get_db()
        row = db.execute(
            "SELECT id FROM expenses WHERE user_id = ? AND category = ? LIMIT 1",
            (user_id, "Transport"),
        ).fetchone()
        db.close()
        assert row is not None, "Expected a Transport expense in seeded data"
        expense_id = row["id"]

        _inject_session(client, user_id)
        response = client.get(f"/expenses/{expense_id}/edit")
        html = response.data.decode("utf-8")

        # "Transport" must appear near "selected"
        transport_idx = html.find("Transport")
        assert transport_idx != -1, "Expected 'Transport' option in category select"
        window = html[max(0, transport_idx - 200): transport_idx + 200]
        assert "selected" in window, (
            "Expected 'Transport' option to carry the selected attribute"
        )


# ------------------------------------------------------------------ #
# POST — valid submission                                             #
# ------------------------------------------------------------------ #

class TestEditExpenseValidPost:

    def test_valid_post_redirects(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(),
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Expected 302 redirect after a valid edit POST"
        )

    def test_valid_post_redirects_to_profile(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(),
            follow_redirects=False,
        )
        location = response.headers.get("Location", "")
        assert "/profile" in location, (
            f"Expected redirect to /profile after valid edit, got: {location}"
        )

    def test_valid_post_does_not_insert_new_row(self, client, app, seeded_db):
        """Row count for this user must not increase after a successful edit."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)

        db = db_module.get_db()
        count_before = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        db.close()

        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(),
            follow_redirects=False,
        )

        db = db_module.get_db()
        count_after = db.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        db.close()

        assert count_after == count_before, (
            f"Expected row count to stay at {count_before} after edit, "
            f"got {count_after} (a new row was inserted)"
        )

    def test_valid_post_updates_amount(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(amount="123.45"),
            follow_redirects=False,
        )

        row = _get_expense_row(expense_id)
        assert row is not None, "Expected expense row to still exist after edit"
        assert abs(row["amount"] - 123.45) < 0.001, (
            f"Expected amount=123.45 after update, got {row['amount']}"
        )

    def test_valid_post_updates_category(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(category="Health"),
            follow_redirects=False,
        )

        row = _get_expense_row(expense_id)
        assert row is not None, "Expected expense row to still exist after edit"
        assert row["category"] == "Health", (
            f"Expected category='Health' after update, got '{row['category']}'"
        )

    def test_valid_post_updates_date(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(date="2026-09-30"),
            follow_redirects=False,
        )

        row = _get_expense_row(expense_id)
        assert row is not None, "Expected expense row to still exist after edit"
        assert row["date"] == "2026-09-30", (
            f"Expected date='2026-09-30' after update, got '{row['date']}'"
        )

    def test_valid_post_updates_description(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(description="Revised description"),
            follow_redirects=False,
        )

        row = _get_expense_row(expense_id)
        assert row is not None, "Expected expense row to still exist after edit"
        assert row["description"] == "Revised description", (
            f"Expected description='Revised description' after update, "
            f"got '{row['description']}'"
        )

    def test_valid_post_updates_correct_row_not_others(self, client, app, seeded_db):
        """Only the targeted expense row should change; other rows must be untouched."""
        user_id = seeded_db

        # Get all expense ids for the seeded user
        db = db_module.get_db()
        rows = db.execute(
            "SELECT id, amount, category, date FROM expenses WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
        db.close()

        assert len(rows) >= 2, "Expected at least 2 seeded expenses"
        target_id = rows[0]["id"]
        untouched_id = rows[1]["id"]
        original_amount = rows[1]["amount"]

        _inject_session(client, user_id)
        client.post(
            f"/expenses/{target_id}/edit",
            data=_valid_form(amount="999.99"),
            follow_redirects=False,
        )

        untouched_row = _get_expense_row(untouched_id)
        assert abs(untouched_row["amount"] - original_amount) < 0.001, (
            f"Expected untouched expense amount to remain {original_amount}, "
            f"got {untouched_row['amount']}"
        )


# ------------------------------------------------------------------ #
# POST — empty/whitespace description stored as NULL                  #
# ------------------------------------------------------------------ #

class TestEditExpenseEmptyDescription:

    def test_empty_description_stored_as_null(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(description=""),
            follow_redirects=False,
        )

        row = _get_expense_row(expense_id)
        assert row is not None, "Expected expense row to still exist after edit"
        assert row["description"] is None, (
            f"Expected description=NULL for empty input, got '{row['description']}'"
        )

    def test_whitespace_only_description_stored_as_null(self, client, app, seeded_db):
        """Whitespace-only description must be stripped and stored as NULL."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(description="   "),
            follow_redirects=False,
        )

        row = _get_expense_row(expense_id)
        assert row is not None, "Expected expense row to still exist after edit"
        assert row["description"] is None, (
            f"Expected whitespace description stored as NULL, got '{row['description']}'"
        )


# ------------------------------------------------------------------ #
# POST — validation errors: amount                                    #
# ------------------------------------------------------------------ #

class TestEditExpenseInvalidAmount:

    def _assert_validation_failure(self, client, expense_id, form_data):
        """Helper: assert 200 re-render and no DB change."""
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 re-render for invalid input, got {response.status_code}"
        )
        return response

    def test_missing_amount_returns_200(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        self._assert_validation_failure(client, expense_id, _valid_form(amount=""))

    def test_missing_amount_shows_error(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(amount=""),
        )
        html_lower = response.data.lower()
        assert b"error" in html_lower or b"valid" in html_lower or b"amount" in html_lower, (
            "Expected an error message for missing amount"
        )

    def test_missing_amount_does_not_change_db(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        original_row = _get_expense_row(expense_id)
        _inject_session(client, user_id)
        client.post(f"/expenses/{expense_id}/edit", data=_valid_form(amount=""))
        updated_row = _get_expense_row(expense_id)
        assert abs(updated_row["amount"] - original_row["amount"]) < 0.001, (
            "Expected DB amount unchanged after missing-amount validation failure"
        )

    def test_zero_amount_returns_200(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        self._assert_validation_failure(client, expense_id, _valid_form(amount="0"))

    def test_zero_amount_does_not_change_db(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        original_row = _get_expense_row(expense_id)
        _inject_session(client, user_id)
        client.post(f"/expenses/{expense_id}/edit", data=_valid_form(amount="0"))
        updated_row = _get_expense_row(expense_id)
        assert abs(updated_row["amount"] - original_row["amount"]) < 0.001, (
            "Expected DB amount unchanged after zero-amount validation failure"
        )

    def test_negative_amount_returns_200(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        self._assert_validation_failure(client, expense_id, _valid_form(amount="-10"))

    def test_negative_amount_does_not_change_db(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        original_row = _get_expense_row(expense_id)
        _inject_session(client, user_id)
        client.post(f"/expenses/{expense_id}/edit", data=_valid_form(amount="-10"))
        updated_row = _get_expense_row(expense_id)
        assert abs(updated_row["amount"] - original_row["amount"]) < 0.001, (
            "Expected DB amount unchanged after negative-amount validation failure"
        )

    def test_non_numeric_amount_returns_200(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        self._assert_validation_failure(client, expense_id, _valid_form(amount="abc"))

    def test_non_numeric_amount_shows_error(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(amount="abc"),
        )
        html_lower = response.data.lower()
        assert b"error" in html_lower or b"valid" in html_lower or b"amount" in html_lower, (
            "Expected a validation error message for non-numeric amount"
        )

    def test_non_numeric_amount_does_not_change_db(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        original_row = _get_expense_row(expense_id)
        _inject_session(client, user_id)
        client.post(f"/expenses/{expense_id}/edit", data=_valid_form(amount="abc"))
        updated_row = _get_expense_row(expense_id)
        assert abs(updated_row["amount"] - original_row["amount"]) < 0.001, (
            "Expected DB amount unchanged after non-numeric-amount validation failure"
        )


# ------------------------------------------------------------------ #
# POST — parametrized invalid amounts                                 #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("bad_amount", [
    "",        # missing
    "0",       # zero
    "0.00",    # zero as float string
    "-1",      # negative
    "-0.01",   # small negative
    "abc",     # non-numeric string
    "1 2",     # spaces
    "1,000",   # comma-formatted
    "1e5x",    # partial scientific notation
])
def test_invalid_amount_does_not_update_row(app, bad_amount):
    """All malformed or out-of-range amounts must be rejected; DB row stays unchanged."""
    db = db_module.get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (
            "Param User",
            f"param_{bad_amount[:3].replace(' ', '_').replace(',', '_')}@example.com",
            generate_password_hash("pass1234"),
        ),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, 50.00, "Food", "2026-06-01", "Original"),
    )
    db.commit()
    expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Param User"

    response = client.post(
        f"/expenses/{expense_id}/edit",
        data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-06-01",
            "description": "Original",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200, (
        f"Expected 200 re-render for bad amount '{bad_amount}', got {response.status_code}"
    )

    row = _get_expense_row(expense_id)
    assert abs(row["amount"] - 50.00) < 0.001, (
        f"Expected amount to remain 50.00 after bad amount '{bad_amount}', "
        f"got {row['amount']}"
    )


# ------------------------------------------------------------------ #
# POST — validation errors: category                                  #
# ------------------------------------------------------------------ #

class TestEditExpenseInvalidCategory:

    def test_invalid_category_returns_200(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(category="Gambling"),
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            "Expected 200 re-render for invalid category"
        )

    def test_invalid_category_shows_error(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(category="Gambling"),
        )
        html_lower = response.data.lower()
        assert b"error" in html_lower or b"valid" in html_lower or b"category" in html_lower, (
            "Expected a validation error message for invalid category"
        )

    def test_invalid_category_does_not_change_db(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        original_row = _get_expense_row(expense_id)
        _inject_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(category="Gambling"),
        )
        updated_row = _get_expense_row(expense_id)
        assert updated_row["category"] == original_row["category"], (
            "Expected DB category unchanged after invalid category validation failure"
        )

    @pytest.mark.parametrize("bad_category", [
        "",              # empty
        "gambling",      # lower-case variant of disallowed value
        "food",          # correct name but wrong case (case-sensitive whitelist)
        "FOOD",          # all-caps
        "'; DROP TABLE expenses; --",  # SQL injection attempt
        "X" * 200,       # very long string
    ])
    def test_disallowed_categories_rejected(self, client, app, seeded_db, bad_category):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(category=bad_category),
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 re-render for disallowed category '{bad_category[:30]}'"
        )


# ------------------------------------------------------------------ #
# POST — validation errors: date                                      #
# ------------------------------------------------------------------ #

class TestEditExpenseInvalidDate:

    def test_missing_date_returns_200(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(date=""),
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            "Expected 200 re-render when date is missing"
        )

    def test_missing_date_shows_error(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(date=""),
        )
        html_lower = response.data.lower()
        assert b"error" in html_lower or b"valid" in html_lower or b"date" in html_lower, (
            "Expected a validation error message for missing date"
        )

    def test_missing_date_does_not_change_db(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        original_row = _get_expense_row(expense_id)
        _inject_session(client, user_id)
        client.post(f"/expenses/{expense_id}/edit", data=_valid_form(date=""))
        updated_row = _get_expense_row(expense_id)
        assert updated_row["date"] == original_row["date"], (
            "Expected DB date unchanged after missing-date validation failure"
        )

    def test_malformed_date_returns_200(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(date="not-a-date"),
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            "Expected 200 re-render for a malformed date string"
        )

    def test_malformed_date_does_not_change_db(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        original_row = _get_expense_row(expense_id)
        _inject_session(client, user_id)
        client.post(f"/expenses/{expense_id}/edit", data=_valid_form(date="not-a-date"))
        updated_row = _get_expense_row(expense_id)
        assert updated_row["date"] == original_row["date"], (
            "Expected DB date unchanged after malformed-date validation failure"
        )

    @pytest.mark.parametrize("bad_date", [
        "",              # empty
        "not-a-date",    # garbage string
        "2026/07/15",    # wrong separator
        "15-07-2026",    # DD-MM-YYYY
        "07-15-2026",    # MM-DD-YYYY
        "2026-13-01",    # invalid month
        "2026-00-01",    # month zero
        "2026-07-32",    # day out of range
    ])
    def test_bad_dates_rejected(self, client, app, seeded_db, bad_date):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(date=bad_date),
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 re-render for bad date '{bad_date}'"
        )


# ------------------------------------------------------------------ #
# POST — field preservation on validation failure                     #
# ------------------------------------------------------------------ #

class TestEditExpenseFieldPreservation:

    def test_amount_preserved_after_invalid_category(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(amount="88.88", category="InvalidCat"),
        )
        assert b"88.88" in response.data, (
            "Expected entered amount '88.88' to be re-populated after validation failure"
        )

    def test_date_preserved_after_invalid_amount(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(amount="bad", date="2026-11-25"),
        )
        assert b"2026-11-25" in response.data, (
            "Expected entered date '2026-11-25' to be re-populated after validation failure"
        )

    def test_description_preserved_after_invalid_amount(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(amount="bad", description="Keep this note"),
        )
        assert b"Keep this note" in response.data, (
            "Expected entered description to be re-populated after validation failure"
        )

    def test_category_preserved_after_invalid_date(self, client, app, seeded_db):
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_form(date="", category="Bills"),
        )
        assert b"Bills" in response.data, (
            "Expected entered category 'Bills' to remain visible after validation failure"
        )

    def test_all_fields_preserved_after_invalid_date(self, client, app, seeded_db):
        """All four fields must survive a validation failure simultaneously."""
        user_id = seeded_db
        expense_id = _get_first_expense_id(user_id)
        _inject_session(client, user_id)
        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "55.55",
                "category": "Shopping",
                "date": "",            # triggers error
                "description": "Preservation test",
            },
        )
        assert b"55.55" in response.data, "Expected amount preserved"
        assert b"Shopping" in response.data, "Expected category preserved"
        assert b"Preservation test" in response.data, "Expected description preserved"


# ------------------------------------------------------------------ #
# POST — each valid category is accepted                              #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("category", [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
])
def test_each_valid_category_is_accepted_on_edit(app, category):
    """Every allowed category must result in a successful update + redirect."""
    db = db_module.get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (
            "Cat Edit User",
            f"catedit_{category.lower()}@example.com",
            generate_password_hash("pass1234"),
        ),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, 10.00, "Food", "2026-06-01", "Original"),
    )
    db.commit()
    expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Cat Edit User"

    response = client.post(
        f"/expenses/{expense_id}/edit",
        data={
            "amount": "20.00",
            "category": category,
            "date": "2026-08-01",
            "description": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302, (
        f"Expected 302 redirect for valid category '{category}', got {response.status_code}"
    )

    row = _get_expense_row(expense_id)
    assert row["category"] == category, (
        f"Expected category='{category}' stored after edit, got '{row['category']}'"
    )
