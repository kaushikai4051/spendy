import pytest
from database.queries import get_summary_stats, get_recent_transactions, get_category_breakdown


# Seeded data (from conftest.py):
#   2026-06-01  Food       ₹50.00   "Lunch"
#   2026-06-02  Food       ₹30.00   "Snack"
#   2026-06-03  Transport  ₹100.00  "Bus pass"
#   2026-06-04  Bills      ₹200.00  "Electricity"
#   Total: ₹380.00 | 3 categories


class TestGetSummaryStatsDateFilter:

    def test_no_filter_returns_all(self, seeded_db, app):
        result = get_summary_stats(seeded_db)
        assert result["transaction_count"] == 4
        assert abs(result["total_spent"] - 380.00) < 0.01

    def test_date_from_filters_correctly(self, seeded_db, app):
        result = get_summary_stats(seeded_db, date_from="2026-06-03")
        assert result["transaction_count"] == 2
        assert abs(result["total_spent"] - 300.00) < 0.01

    def test_date_to_filters_correctly(self, seeded_db, app):
        result = get_summary_stats(seeded_db, date_to="2026-06-02")
        assert result["transaction_count"] == 2
        assert abs(result["total_spent"] - 80.00) < 0.01

    def test_date_range_filters_correctly(self, seeded_db, app):
        result = get_summary_stats(seeded_db, date_from="2026-06-02", date_to="2026-06-03")
        assert result["transaction_count"] == 2
        assert abs(result["total_spent"] - 130.00) < 0.01

    def test_no_results_in_range(self, seeded_db, app):
        result = get_summary_stats(seeded_db, date_from="2020-01-01", date_to="2020-12-31")
        assert result["transaction_count"] == 0
        assert result["total_spent"] == 0.0
        assert result["top_category"] == "—"

    def test_top_category_respects_filter(self, seeded_db, app):
        result = get_summary_stats(seeded_db, date_from="2026-06-01", date_to="2026-06-02")
        assert result["top_category"] == "Food"


class TestGetRecentTransactionsDateFilter:

    def test_no_filter_returns_all(self, seeded_db, app):
        result = get_recent_transactions(seeded_db)
        assert len(result) == 4

    def test_date_from_filters_correctly(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_from="2026-06-03")
        assert len(result) == 2
        assert all(r["date"] >= "2026-06-03" for r in result)

    def test_date_to_filters_correctly(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_to="2026-06-02")
        assert len(result) == 2
        assert all(r["date"] <= "2026-06-02" for r in result)

    def test_date_range_filters_correctly(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_from="2026-06-02", date_to="2026-06-03")
        assert len(result) == 2

    def test_limit_still_respected_with_filter(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, limit=2, date_from="2026-06-01")
        assert len(result) == 2

    def test_empty_range_returns_empty_list(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_from="2020-01-01", date_to="2020-12-31")
        assert result == []

    def test_newest_first_within_filter(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_from="2026-06-01", date_to="2026-06-04")
        dates = [r["date"] for r in result]
        assert dates == sorted(dates, reverse=True)


class TestGetCategoryBreakdownDateFilter:

    def test_no_filter_returns_all_categories(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        assert len(result) == 3

    def test_date_range_reduces_categories(self, seeded_db, app):
        result = get_category_breakdown(seeded_db, date_from="2026-06-01", date_to="2026-06-02")
        assert len(result) == 1
        assert result[0]["name"] == "Food"

    def test_pct_sums_to_100_with_filter(self, seeded_db, app):
        result = get_category_breakdown(seeded_db, date_from="2026-06-02", date_to="2026-06-04")
        assert sum(r["pct"] for r in result) == 100

    def test_amounts_correct_with_filter(self, seeded_db, app):
        result = get_category_breakdown(seeded_db, date_from="2026-06-03", date_to="2026-06-04")
        names = {r["name"]: r["amount"] for r in result}
        assert abs(names["Bills"] - 200.00) < 0.01
        assert abs(names["Transport"] - 100.00) < 0.01

    def test_empty_range_returns_empty_list(self, seeded_db, app):
        result = get_category_breakdown(seeded_db, date_from="2020-01-01", date_to="2020-12-31")
        assert result == []


class TestProfileRouteDateFilter:

    def _login(self, client, seeded_db):
        with client.session_transaction() as sess:
            sess["user_id"] = seeded_db
            sess["user_name"] = "Test User"

    def test_no_filter_shows_full_data(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile")
        assert response.status_code == 200
        assert b"380.00" in response.data

    def test_filter_applied_reduces_total(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-02")
        assert response.status_code == 200
        assert b"80.00" in response.data

    def test_filter_applied_shows_correct_transactions(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile?from=2026-06-03&to=2026-06-03")
        assert b"Bus pass" in response.data
        assert b"Electricity" not in response.data

    def test_invalid_from_param_ignored(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile?from=not-a-date&to=2026-06-04")
        assert response.status_code == 200
        assert b"380.00" in response.data

    def test_swapped_dates_normalised(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile?from=2026-06-04&to=2026-06-01")
        assert response.status_code == 200
        assert b"380.00" in response.data

    def test_date_inputs_pre_filled(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-03")
        assert b'value="2026-06-01"' in response.data
        assert b'value="2026-06-03"' in response.data

    def test_clear_link_shown_when_filter_active(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile?from=2026-06-01")
        assert b"Clear" in response.data

    def test_clear_link_not_shown_without_filter(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile")
        assert b"Clear" not in response.data

    def test_filter_label_shown_when_active(self, client, seeded_db):
        self._login(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-03")
        assert b"Showing:" in response.data

    def test_redirect_when_not_logged_in(self, client):
        response = client.get("/profile?from=2026-06-01&to=2026-06-04")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
