import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """Flask test app backed by a temporary SQLite file."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    import database.db as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_path

    from app import app as flask_app
    flask_app.config["TESTING"] = True

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
    Inserts one user and 4 known expenses. Returns user_id.

    User:  name="Test User", email="test@example.com", created_at="2025-01-15 10:00:00"
    Food      ₹50.00   2026-06-01  "Lunch"
    Food      ₹30.00   2026-06-02  "Snack"
    Transport ₹100.00  2026-06-03  "Bus pass"
    Bills     ₹200.00  2026-06-04  "Electricity"
    Total: ₹380.00  |  top_category: Bills  |  3 categories
    """
    import database.db as db_module
    db = db_module.get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Test User", "test@example.com",
         generate_password_hash("password123"), "2025-01-15 10:00:00"),
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
