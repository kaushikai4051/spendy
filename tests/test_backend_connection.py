import pytest
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ================================================================== #
# SUB-AGENT-2: TestGetUserById + TestGetSummaryStats                  #
# ================================================================== #

class TestGetUserById:
    def test_returns_dict(self, seeded_db, app):
        result = get_user_by_id(seeded_db)
        assert isinstance(result, dict)

    def test_keys_present(self, seeded_db, app):
        result = get_user_by_id(seeded_db)
        assert set(result.keys()) == {"name", "email", "member_since"}

    def test_correct_name(self, seeded_db, app):
        result = get_user_by_id(seeded_db)
        assert result["name"] == "Test User"

    def test_member_since_format(self, seeded_db, app):
        result = get_user_by_id(seeded_db)
        assert result["member_since"] == "January 2025"

    def test_unknown_user_returns_defaults(self, app):
        result = get_user_by_id(999999)
        assert result["name"] == ""
        assert result["member_since"] == "Unknown"


class TestGetSummaryStats:
    def test_returns_dict(self, seeded_db, app):
        result = get_summary_stats(seeded_db)
        assert isinstance(result, dict)

    def test_keys_present(self, seeded_db, app):
        result = get_summary_stats(seeded_db)
        assert set(result.keys()) == {"transaction_count", "total_spent", "top_category"}

    def test_transaction_count(self, seeded_db, app):
        result = get_summary_stats(seeded_db)
        assert result["transaction_count"] == 4

    def test_total_spent(self, seeded_db, app):
        result = get_summary_stats(seeded_db)
        assert abs(result["total_spent"] - 380.00) < 0.01

    def test_top_category(self, seeded_db, app):
        result = get_summary_stats(seeded_db)
        assert result["top_category"] == "Bills"

    def test_no_expenses_returns_zeros(self, app):
        import database.db as db_module
        db = db_module.get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty", "empty_stats@example.com", "x"),
        )
        db.commit()
        uid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()
        result = get_summary_stats(uid)
        assert result["transaction_count"] == 0
        assert result["total_spent"] == 0.0
        assert result["top_category"] == "—"

# END SUB-AGENT-2
# ================================================================== #


# ================================================================== #
# SUB-AGENT-1: TestGetRecentTransactions + TestProfileRouteGet        #
# ================================================================== #

class TestGetRecentTransactions:
    def test_returns_list(self, seeded_db, app):
        result = get_recent_transactions(seeded_db)
        assert isinstance(result, list)

    def test_correct_count(self, seeded_db, app):
        result = get_recent_transactions(seeded_db)
        assert len(result) == 4

    def test_newest_first(self, seeded_db, app):
        result = get_recent_transactions(seeded_db)
        dates = [r["date"] for r in result]
        assert dates == sorted(dates, reverse=True)

    def test_dict_keys(self, seeded_db, app):
        result = get_recent_transactions(seeded_db)
        assert set(result[0].keys()) == {"id", "date", "description", "category", "amount"}

    def test_amount_is_float(self, seeded_db, app):
        result = get_recent_transactions(seeded_db)
        assert isinstance(result[0]["amount"], float)

    def test_empty_when_no_expenses(self, app):
        import database.db as db_module
        db = db_module.get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty", "empty_txn@example.com", "x"),
        )
        db.commit()
        uid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()
        assert get_recent_transactions(uid) == []

    def test_limit_respected(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, limit=2)
        assert len(result) == 2


class TestProfileRouteGet:
    def test_redirects_if_not_logged_in(self, client):
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_profile_page_loads(self, client, seeded_db):
        with client.session_transaction() as sess:
            sess["user_id"] = seeded_db
            sess["user_name"] = "Test User"
        response = client.get("/profile")
        assert response.status_code == 200

    def test_recent_transactions_heading_in_response(self, client, seeded_db):
        with client.session_transaction() as sess:
            sess["user_id"] = seeded_db
            sess["user_name"] = "Test User"
        response = client.get("/profile")
        assert b"Recent Transactions" in response.data

    def test_rupee_symbol_in_page(self, client, seeded_db):
        with client.session_transaction() as sess:
            sess["user_id"] = seeded_db
            sess["user_name"] = "Test User"
        response = client.get("/profile")
        assert "₹".encode("utf-8") in response.data

# END SUB-AGENT-1
# ================================================================== #


# ================================================================== #
# SUB-AGENT-3: TestGetCategoryBreakdown                               #
# ================================================================== #

class TestGetCategoryBreakdown:
    def test_returns_list(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        assert isinstance(result, list)

    def test_correct_category_count(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        assert len(result) == 3

    def test_dict_keys(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        assert set(result[0].keys()) == {"name", "amount", "pct"}

    def test_pct_sums_to_100(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        assert sum(r["pct"] for r in result) == 100

    def test_pct_is_int(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        for r in result:
            assert isinstance(r["pct"], int)

    def test_ordered_by_amount_desc(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        amounts = [r["amount"] for r in result]
        assert amounts == sorted(amounts, reverse=True)

    def test_bills_is_first(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        assert result[0]["name"] == "Bills"
        assert abs(result[0]["amount"] - 200.00) < 0.01

    def test_empty_when_no_expenses(self, app):
        import database.db as db_module
        db = db_module.get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty", "empty_cat@example.com", "x"),
        )
        db.commit()
        uid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()
        assert get_category_breakdown(uid) == []

# END SUB-AGENT-3
# ================================================================== #
