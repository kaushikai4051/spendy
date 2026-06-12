"""
Tests for Step 09: Delete Expense
==================================
Spec source: .claude/specs/09-delete-expense.md

Behaviors covered:
  - Importability: delete_expense is importable from database.db
  - Auth guard: unauthenticated POST redirects to /login
  - HTTP method guard: GET to /expenses/<id>/delete returns 405
  - Happy path: valid POST removes the row from the DB
  - Happy path: redirect goes to /profile after delete
  - Happy path: profile page no longer shows the deleted expense
  - Ownership guard: POST targeting another user's expense redirects to /profile
  - Ownership guard: cross-user delete attempt leaves the target row untouched
  - Idempotence: POST to a non-existent expense ID silently redirects to /profile
  - Only targeted row removed: other expenses for the same user remain intact
  - Delete button visible on /profile: form with POST method present in page HTML
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


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _inject_session(client, user_id: int, user_name: str = "Test User"):
    """Set session variables directly without hitting the login route."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = user_name


def _get_all_expense_ids(user_id: int) -> list:
    """Return all expense IDs for user_id, ordered by id ASC."""
    db = db_module.get_db()
    rows = db.execute(
        "SELECT id FROM expenses WHERE user_id = ? ORDER BY id ASC",
        (user_id,),
    ).fetchall()
    db.close()
    return [row["id"] for row in rows]


def _get_expense_row(expense_id: int):
    """Fetch a single expense row by id; returns sqlite3.Row or None."""
    db = db_module.get_db()
    row = db.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    db.close()
    return row


def _count_expenses(user_id: int) -> int:
    """Return the total number of expenses rows for user_id."""
    db = db_module.get_db()
    count = db.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    db.close()
    return count


# ------------------------------------------------------------------ #
# Importability                                                       #
# ------------------------------------------------------------------ #

class TestDeleteExpenseImportability:

    def test_delete_expense_is_importable_from_db_module(self):
        """delete_expense must be importable from database.db."""
        from database.db import delete_expense  # noqa: F401
        assert callable(delete_expense), (
            "delete_expense must be a callable function in database.db"
        )

    def test_delete_expense_accepts_expense_id_and_user_id(self):
        """delete_expense(expense_id, user_id) must accept two positional arguments."""
        from database.db import delete_expense
        import inspect
        sig = inspect.signature(delete_expense)
        params = list(sig.parameters.keys())
        assert len(params) >= 2, (
            f"delete_expense must accept at least 2 parameters (expense_id, user_id), "
            f"got: {params}"
        )


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestDeleteExpenseAuthGuard:

    def test_unauthenticated_post_redirects(self, client, app, seeded_db):
        """POST without a session must return 302."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        assert expense_ids, "Expected at least one seeded expense"
        expense_id = expense_ids[0]

        response = client.post(
            f"/expenses/{expense_id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 for unauthenticated POST, got {response.status_code}"
        )

    def test_unauthenticated_post_redirects_to_login(self, client, app, seeded_db):
        """POST without a session must redirect to /login."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]

        response = client.post(
            f"/expenses/{expense_id}/delete",
            follow_redirects=False,
        )
        location = response.headers.get("Location", "")
        assert "/login" in location, (
            f"Unauthenticated POST must redirect to /login, got Location: {location}"
        )

    def test_unauthenticated_post_does_not_delete_expense(self, client, app, seeded_db):
        """An unauthenticated request must not remove any row from the DB."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]

        client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

        row = _get_expense_row(expense_id)
        assert row is not None, (
            "Unauthenticated POST must not delete the expense row"
        )


# ------------------------------------------------------------------ #
# HTTP method guard                                                   #
# ------------------------------------------------------------------ #

class TestDeleteExpenseHttpMethod:

    def test_get_returns_405(self, client, app, seeded_db):
        """GET to the delete URL must return 405 Method Not Allowed."""
        user_id = seeded_db
        _inject_session(client, user_id)
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]

        response = client.get(
            f"/expenses/{expense_id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 405, (
            f"Expected 405 for GET on delete URL, got {response.status_code}"
        )

    def test_get_returns_405_even_when_not_logged_in(self, client, app, seeded_db):
        """GET must be rejected as 405 regardless of authentication state."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]

        response = client.get(
            f"/expenses/{expense_id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 405, (
            f"Expected 405 Method Not Allowed for GET (unauthenticated), "
            f"got {response.status_code}"
        )


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #

class TestDeleteExpenseHappyPath:

    def test_valid_post_returns_302(self, client, app, seeded_db):
        """Authenticated POST on an owned expense must return 302."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]
        _inject_session(client, user_id)

        response = client.post(
            f"/expenses/{expense_id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 after successful delete, got {response.status_code}"
        )

    def test_valid_post_redirects_to_profile(self, client, app, seeded_db):
        """After a successful delete, the redirect must point to /profile."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]
        _inject_session(client, user_id)

        response = client.post(
            f"/expenses/{expense_id}/delete",
            follow_redirects=False,
        )
        location = response.headers.get("Location", "")
        assert "/profile" in location, (
            f"Expected redirect to /profile after delete, got Location: {location}"
        )

    def test_valid_post_removes_row_from_db(self, client, app, seeded_db):
        """The deleted expense row must not exist in the DB after a successful POST."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]
        _inject_session(client, user_id)

        client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

        row = _get_expense_row(expense_id)
        assert row is None, (
            f"Expected expense id={expense_id} to be removed from DB after delete, "
            f"but the row still exists"
        )

    def test_deleted_expense_absent_on_profile_page(self, client, app, seeded_db):
        """After following the redirect to /profile, deleted expense must not appear."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]
        _inject_session(client, user_id)

        # Verify the description exists before deletion
        row_before = _get_expense_row(expense_id)
        assert row_before is not None, "Expected expense to exist before delete"
        description = row_before["description"]

        # Delete and follow to profile
        client.post(f"/expenses/{expense_id}/delete", follow_redirects=True)

        # Profile should not show this expense's description any more
        profile_response = client.get("/profile")
        assert profile_response.status_code == 200, (
            "Expected /profile to return 200 after delete"
        )
        if description:
            # Only assert absence if the description is unique enough to check
            # (checking that the page no longer lists this specific description)
            db = db_module.get_db()
            remaining = db.execute(
                "SELECT COUNT(*) FROM expenses WHERE description = ? AND user_id = ?",
                (description, user_id),
            ).fetchone()[0]
            db.close()
            # If no other expense has the same description, it should not appear
            if remaining == 0:
                assert description.encode() not in profile_response.data, (
                    f"Expected deleted expense description '{description}' "
                    f"to be absent from /profile after delete"
                )


# ------------------------------------------------------------------ #
# Only the targeted row is removed                                    #
# ------------------------------------------------------------------ #

class TestDeleteExpenseIsolation:

    def test_only_targeted_expense_is_deleted(self, client, app, seeded_db):
        """Deleting one expense must not affect the other expenses of the same user."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        assert len(expense_ids) >= 2, "Expected at least 2 seeded expenses"

        target_id = expense_ids[0]
        surviving_ids = expense_ids[1:]
        _inject_session(client, user_id)

        client.post(f"/expenses/{target_id}/delete", follow_redirects=False)

        for surviving_id in surviving_ids:
            row = _get_expense_row(surviving_id)
            assert row is not None, (
                f"Expected expense id={surviving_id} to survive after "
                f"deleting expense id={target_id}"
            )

    def test_expense_count_decreases_by_exactly_one(self, client, app, seeded_db):
        """Row count for the user must drop by exactly 1 after a single delete."""
        user_id = seeded_db
        count_before = _count_expenses(user_id)
        expense_ids = _get_all_expense_ids(user_id)
        target_id = expense_ids[0]
        _inject_session(client, user_id)

        client.post(f"/expenses/{target_id}/delete", follow_redirects=False)

        count_after = _count_expenses(user_id)
        assert count_after == count_before - 1, (
            f"Expected expense count to drop from {count_before} to "
            f"{count_before - 1}, got {count_after}"
        )

    def test_last_expense_can_be_deleted(self, client, app, seeded_db):
        """Deleting all expenses one by one must work without errors."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        _inject_session(client, user_id)

        for expense_id in expense_ids:
            response = client.post(
                f"/expenses/{expense_id}/delete",
                follow_redirects=False,
            )
            assert response.status_code == 302, (
                f"Expected 302 when deleting expense id={expense_id}, "
                f"got {response.status_code}"
            )

        assert _count_expenses(user_id) == 0, (
            "Expected all expenses to be removed after sequential deletes"
        )


# ------------------------------------------------------------------ #
# Ownership guard                                                     #
# ------------------------------------------------------------------ #

class TestDeleteExpenseOwnership:

    def _create_second_user_with_expense(self):
        """Insert a second user and one expense for them. Returns (user_id, expense_id)."""
        db = db_module.get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other User", "other@example.com", generate_password_hash("pass5678")),
        )
        db.commit()
        other_user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (other_user_id, 77.77, "Food", "2026-07-01", "Other user lunch"),
        )
        db.commit()
        other_expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()
        return other_user_id, other_expense_id

    def test_cross_user_delete_redirects_to_profile(self, client, app, seeded_db):
        """POSTing to another user's expense must redirect to /profile."""
        _, other_expense_id = self._create_second_user_with_expense()
        _inject_session(client, seeded_db)  # logged in as user 1

        response = client.post(
            f"/expenses/{other_expense_id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 when attempting cross-user delete, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "/profile" in location, (
            f"Cross-user delete must redirect to /profile, got Location: {location}"
        )

    def test_cross_user_delete_does_not_remove_row(self, client, app, seeded_db):
        """The target row must remain in the DB after a cross-user delete attempt."""
        _, other_expense_id = self._create_second_user_with_expense()
        _inject_session(client, seeded_db)  # logged in as user 1

        client.post(
            f"/expenses/{other_expense_id}/delete",
            follow_redirects=False,
        )

        row = _get_expense_row(other_expense_id)
        assert row is not None, (
            f"Expected expense id={other_expense_id} (belonging to another user) "
            f"to remain in DB after a cross-user delete attempt"
        )

    def test_cross_user_delete_does_not_affect_own_expenses(self, client, app, seeded_db):
        """The logged-in user's own expenses must be untouched after a failed cross-user delete."""
        _, other_expense_id = self._create_second_user_with_expense()
        own_count_before = _count_expenses(seeded_db)
        _inject_session(client, seeded_db)

        client.post(
            f"/expenses/{other_expense_id}/delete",
            follow_redirects=False,
        )

        own_count_after = _count_expenses(seeded_db)
        assert own_count_after == own_count_before, (
            f"Expected own expense count to remain {own_count_before} "
            f"after cross-user delete attempt, got {own_count_after}"
        )


# ------------------------------------------------------------------ #
# Idempotence — non-existent expense ID                               #
# ------------------------------------------------------------------ #

class TestDeleteExpenseIdempotence:

    def test_nonexistent_id_redirects_to_profile(self, client, app, seeded_db):
        """POSTing a delete for a non-existent ID must silently redirect to /profile."""
        _inject_session(client, seeded_db)

        response = client.post(
            "/expenses/999999/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 for delete of non-existent expense, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "/profile" in location, (
            f"Expected redirect to /profile for non-existent ID, got Location: {location}"
        )

    def test_nonexistent_id_does_not_raise_error(self, client, app, seeded_db):
        """Delete of a non-existent ID must produce no 4xx/5xx error response."""
        _inject_session(client, seeded_db)

        response = client.post(
            "/expenses/999999/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200, (
            f"Expected 200 after following redirect for non-existent ID delete, "
            f"got {response.status_code}"
        )

    def test_double_delete_is_idempotent(self, client, app, seeded_db):
        """Deleting the same expense twice must not raise an error on the second call."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        expense_id = expense_ids[0]
        _inject_session(client, user_id)

        # First delete — removes the row
        response1 = client.post(
            f"/expenses/{expense_id}/delete",
            follow_redirects=False,
        )
        assert response1.status_code == 302, (
            f"Expected 302 on first delete, got {response1.status_code}"
        )

        # Second delete — row already gone; must still redirect gracefully
        response2 = client.post(
            f"/expenses/{expense_id}/delete",
            follow_redirects=False,
        )
        assert response2.status_code == 302, (
            f"Expected 302 on second delete of already-deleted expense, "
            f"got {response2.status_code}"
        )
        location = response2.headers.get("Location", "")
        assert "/profile" in location, (
            f"Expected second delete to redirect to /profile, got Location: {location}"
        )


# ------------------------------------------------------------------ #
# Delete button visible on /profile                                   #
# ------------------------------------------------------------------ #

class TestDeleteButtonOnProfile:

    def test_profile_page_contains_delete_form(self, client, app, seeded_db):
        """GET /profile must render at least one delete form with method=POST."""
        user_id = seeded_db
        _inject_session(client, user_id)

        response = client.get("/profile")
        assert response.status_code == 200, (
            "Expected /profile to return 200 for authenticated user"
        )
        html = response.data.decode("utf-8").lower()
        # The delete form must use POST; look for method="post" in the HTML
        assert 'method="post"' in html or "method='post'" in html, (
            "Expected at least one <form method='POST'> on /profile for the delete action"
        )

    def test_profile_page_contains_delete_url_for_each_expense(self, client, app, seeded_db):
        """Each expense row's delete form action must point to /expenses/<id>/delete."""
        user_id = seeded_db
        expense_ids = _get_all_expense_ids(user_id)
        _inject_session(client, user_id)

        response = client.get("/profile")
        assert response.status_code == 200, "Expected /profile to return 200"
        html = response.data.decode("utf-8")

        for expense_id in expense_ids:
            expected_action = f"/expenses/{expense_id}/delete"
            assert expected_action in html, (
                f"Expected delete form action '{expected_action}' "
                f"to be present in /profile HTML"
            )

    def test_profile_page_contains_delete_button_element(self, client, app, seeded_db):
        """The delete action must be triggered by a button or submit input element."""
        user_id = seeded_db
        _inject_session(client, user_id)

        response = client.get("/profile")
        assert response.status_code == 200, "Expected /profile to return 200"
        html_lower = response.data.decode("utf-8").lower()

        has_submit_button = (
            '<button' in html_lower
            or 'type="submit"' in html_lower
            or "type='submit'" in html_lower
        )
        assert has_submit_button, (
            "Expected a submit button or input[type=submit] on /profile for delete"
        )

    def test_profile_page_no_javascript_required_for_delete(self, client, app, seeded_db):
        """Delete must be a plain HTML form POST — the form action must contain /delete."""
        user_id = seeded_db
        _inject_session(client, user_id)

        response = client.get("/profile")
        assert response.status_code == 200, "Expected /profile to return 200"
        html = response.data.decode("utf-8")

        assert "/delete" in html, (
            "Expected the string '/delete' to appear in the profile page HTML, "
            "indicating a plain-form delete button (no JS required)"
        )


# ------------------------------------------------------------------ #
# Parametrized: delete every seeded expense by index                  #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("expense_index", [0, 1, 2, 3])
def test_each_seeded_expense_can_be_deleted(app, expense_index):
    """
    Each of the 4 seeded expenses can be individually deleted.
    Verifies the ownership-scoped DELETE query works for every row.
    """
    db = db_module.get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (
            f"Param User {expense_index}",
            f"paramdelete_{expense_index}@example.com",
            generate_password_hash("pass1234"),
            "2025-01-01 00:00:00",
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
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    db.commit()
    all_rows = db.execute(
        "SELECT id FROM expenses WHERE user_id = ? ORDER BY id ASC", (user_id,)
    ).fetchall()
    db.close()

    target_id = all_rows[expense_index]["id"]

    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = f"Param User {expense_index}"

    response = test_client.post(
        f"/expenses/{target_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 302, (
        f"Expected 302 after deleting expense at index {expense_index}, "
        f"got {response.status_code}"
    )

    row = _get_expense_row(target_id)
    assert row is None, (
        f"Expected expense id={target_id} (index {expense_index}) to be "
        f"removed from DB, but row still exists"
    )
