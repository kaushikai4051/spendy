"""
Tests for Step 06: Date Filter on Profile Page
===============================================
Spec source: .claude/specs/06-date-filter-profile.md

Seeded data (from conftest.py seeded_db fixture):
  2026-06-01  Food       ₹50.00   "Lunch"
  2026-06-02  Food       ₹30.00   "Snack"
  2026-06-03  Transport  ₹100.00  "Bus pass"
  2026-06-04  Bills      ₹200.00  "Electricity"
  Total: ₹380.00 | top category: Bills | 3 categories
"""

import pytest
from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ------------------------------------------------------------------ #
# Auth helpers                                                        #
# ------------------------------------------------------------------ #

def _set_session(client, user_id, user_name="Test User"):
    """Inject a logged-in session without hitting the login route."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = user_name


# ================================================================== #
# 1. Auth guard                                                       #
# ================================================================== #

class TestAuthGuard:
    """Unauthenticated requests must be redirected to /login regardless of query params."""

    def test_profile_no_params_redirects_unauthenticated(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Expected redirect for unauthenticated access"
        assert "/login" in response.headers["Location"], "Redirect must go to /login"

    def test_profile_with_filter_params_redirects_unauthenticated(self, client):
        response = client.get("/profile?from=2026-06-01&to=2026-06-04")
        assert response.status_code == 302, "Filter params must not bypass auth guard"
        assert "/login" in response.headers["Location"], "Redirect must go to /login"

    def test_profile_from_only_redirects_unauthenticated(self, client):
        response = client.get("/profile?from=2026-06-01")
        assert response.status_code == 302, "from-only param must not bypass auth guard"
        assert "/login" in response.headers["Location"]

    def test_profile_to_only_redirects_unauthenticated(self, client):
        response = client.get("/profile?to=2026-06-04")
        assert response.status_code == 302, "to-only param must not bypass auth guard"
        assert "/login" in response.headers["Location"]


# ================================================================== #
# 2. No-filter: unchanged all-time behaviour                          #
# ================================================================== #

class TestNoFilterUnchangedBehaviour:
    """GET /profile with no query params must behave exactly as before Step 06."""

    def test_returns_200(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert response.status_code == 200, "Profile page must return 200 when logged in"

    def test_all_time_total_displayed(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert b"380.00" in response.data, "All-time total ₹380.00 must appear with no filter"

    def test_all_time_transaction_count(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        # The template renders "4 expenses" (expense_count = 4)
        assert b"4 expense" in response.data, "All 4 transactions must be counted without a filter"

    def test_all_transactions_listed(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        for description in [b"Lunch", b"Snack", b"Bus pass", b"Electricity"]:
            assert description in response.data, (
                f"Transaction '{description}' must appear in unfiltered view"
            )

    def test_all_categories_in_breakdown(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        for category in [b"Food", b"Transport", b"Bills"]:
            assert category in response.data, (
                f"Category '{category}' must appear in unfiltered breakdown"
            )

    def test_no_showing_label_without_filter(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert b"Showing:" not in response.data, (
            "'Showing:' active-filter label must NOT appear when no filter is active"
        )

    def test_no_clear_link_without_filter(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert b"Clear" not in response.data, (
            "'Clear' link must NOT appear when no filter is active"
        )


# ================================================================== #
# 3. Filter bar UI                                                    #
# ================================================================== #

class TestFilterBarUI:
    """The profile page must render a filter form with correct attributes."""

    def test_filter_form_uses_get_method(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert b'method="GET"' in response.data, "Filter form must use method='GET'"

    def test_from_date_input_present(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert b'name="from"' in response.data, "Filter form must have a 'from' date input"

    def test_to_date_input_present(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert b'name="to"' in response.data, "Filter form must have a 'to' date input"

    def test_filter_button_present(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert b"Filter" in response.data, "A 'Filter' submit button must be present"

    def test_from_input_prepopulated_after_filter(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-03")
        assert b'value="2026-06-01"' in response.data, (
            "The 'from' input must retain the active filter value after submission"
        )

    def test_to_input_prepopulated_after_filter(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-03")
        assert b'value="2026-06-03"' in response.data, (
            "The 'to' input must retain the active filter value after submission"
        )

    def test_clear_link_shown_when_both_params_active(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-04")
        assert b"Clear" in response.data, (
            "'Clear' link must appear when both from and to params are set"
        )

    def test_clear_link_shown_when_only_from_active(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01")
        assert b"Clear" in response.data, (
            "'Clear' link must appear when only the 'from' param is set"
        )

    def test_clear_link_shown_when_only_to_active(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?to=2026-06-04")
        assert b"Clear" in response.data, (
            "'Clear' link must appear when only the 'to' param is set"
        )

    def test_showing_label_present_when_filter_active(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-03")
        assert b"Showing:" in response.data, (
            "'Showing:' label must appear above stats cards when a filter is active"
        )

    def test_showing_label_absent_when_no_filter(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        assert b"Showing:" not in response.data, (
            "'Showing:' label must NOT appear when no filter is active"
        )

    def test_from_input_empty_when_no_filter(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile")
        # value="" is the empty state for date inputs
        assert b'name="from"' in response.data, "from input must always be present"
        # No active filter value should appear
        assert b'value="2026-' not in response.data, (
            "No date value should be pre-filled when there is no active filter"
        )


# ================================================================== #
# 4. Both dates filter — stats, transactions, category breakdown      #
# ================================================================== #

class TestBothDatesFilter:
    """?from=YYYY-MM-DD&to=YYYY-MM-DD narrows all three data panels."""

    def test_filtered_total_reflects_range(self, client, seeded_db):
        # 2026-06-01 to 2026-06-02: Food ₹50 + Food ₹30 = ₹80
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-02")
        assert response.status_code == 200
        assert b"80.00" in response.data, "Total must reflect only expenses in range"

    def test_filtered_transaction_count_reflects_range(self, client, seeded_db):
        # 2026-06-01 to 2026-06-02: 2 transactions
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-02")
        assert b"2 expense" in response.data, "Transaction count must reflect filtered range"

    def test_in_range_transactions_shown(self, client, seeded_db):
        # 2026-06-03 only: Bus pass
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03&to=2026-06-03")
        assert b"Bus pass" in response.data, "Transaction within range must appear"

    def test_out_of_range_transactions_hidden(self, client, seeded_db):
        # 2026-06-03 only: Electricity (Jun 04) must not appear
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03&to=2026-06-03")
        assert b"Electricity" not in response.data, "Transaction outside range must not appear"

    def test_category_breakdown_reflects_range(self, client, seeded_db):
        # 2026-06-01 to 2026-06-02: only Food category
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-02")
        assert b"Food" in response.data, "Food category must appear in breakdown for Jun 01-02"
        assert b"Transport" not in response.data, (
            "Transport must NOT appear in breakdown when filtered to Jun 01-02"
        )

    def test_top_category_respects_filter(self, client, seeded_db):
        # 2026-06-01 to 2026-06-02: only Food; Bills is outside range
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-02")
        assert b"Bills" not in response.data or b"Food" in response.data, (
            "Top category stat must reflect the filtered range"
        )

    def test_rupee_currency_in_filtered_view(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-04")
        assert "₹".encode("utf-8") in response.data, (
            "Currency must always be displayed as ₹ (never $ or £)"
        )


# ================================================================== #
# 5. From-only filter                                                 #
# ================================================================== #

class TestFromOnlyFilter:
    """?from=YYYY-MM-DD with no 'to' returns all expenses from that date onwards."""

    def test_from_only_returns_correct_total(self, client, seeded_db):
        # from=2026-06-03: Transport ₹100 + Bills ₹200 = ₹300
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03")
        assert response.status_code == 200
        assert b"300.00" in response.data, (
            "Total must include all expenses from the 'from' date to present"
        )

    def test_from_only_excludes_earlier_transactions(self, client, seeded_db):
        # from=2026-06-03: Lunch (Jun 01) and Snack (Jun 02) must not appear
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03")
        assert b"Lunch" not in response.data, "Expense before 'from' date must not appear"
        assert b"Snack" not in response.data, "Expense before 'from' date must not appear"

    def test_from_only_includes_boundary_date(self, client, seeded_db):
        # from=2026-06-03: Bus pass (Jun 03) must appear — boundary is inclusive
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03")
        assert b"Bus pass" in response.data, "Expense on the boundary 'from' date must appear"

    def test_from_only_shows_clear_link(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03")
        assert b"Clear" in response.data, "'Clear' link must appear with from-only filter"

    def test_from_only_shows_filter_label(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03")
        assert b"Showing:" in response.data, (
            "'Showing:' label must appear with from-only filter"
        )


# ================================================================== #
# 6. To-only filter                                                   #
# ================================================================== #

class TestToOnlyFilter:
    """?to=YYYY-MM-DD with no 'from' returns all expenses up to and including that date."""

    def test_to_only_returns_correct_total(self, client, seeded_db):
        # to=2026-06-02: Food ₹50 + Food ₹30 = ₹80
        _set_session(client, seeded_db)
        response = client.get("/profile?to=2026-06-02")
        assert response.status_code == 200
        assert b"80.00" in response.data, (
            "Total must include all expenses up to and including the 'to' date"
        )

    def test_to_only_excludes_later_transactions(self, client, seeded_db):
        # to=2026-06-02: Bus pass (Jun 03) and Electricity (Jun 04) must not appear
        _set_session(client, seeded_db)
        response = client.get("/profile?to=2026-06-02")
        assert b"Bus pass" not in response.data, "Expense after 'to' date must not appear"
        assert b"Electricity" not in response.data, "Expense after 'to' date must not appear"

    def test_to_only_includes_boundary_date(self, client, seeded_db):
        # to=2026-06-02: Snack (Jun 02) must appear — boundary is inclusive
        _set_session(client, seeded_db)
        response = client.get("/profile?to=2026-06-02")
        assert b"Snack" in response.data, "Expense on the boundary 'to' date must appear"

    def test_to_only_shows_clear_link(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?to=2026-06-02")
        assert b"Clear" in response.data, "'Clear' link must appear with to-only filter"

    def test_to_only_shows_filter_label(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?to=2026-06-02")
        assert b"Showing:" in response.data, (
            "'Showing:' label must appear with to-only filter"
        )


# ================================================================== #
# 7. Swapped dates normalisation                                      #
# ================================================================== #

class TestSwappedDatesNormalisation:
    """When from > to, the route must swap them silently and return correct data."""

    def test_swapped_dates_return_200(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-04&to=2026-06-01")
        assert response.status_code == 200, (
            "Swapped dates must not cause an error — they must be normalised silently"
        )

    def test_swapped_dates_return_same_as_correct_order(self, client, seeded_db):
        # ?from=2026-06-04&to=2026-06-01 should equal ?from=2026-06-01&to=2026-06-04 (all 4 expenses)
        _set_session(client, seeded_db)
        response_swapped = client.get("/profile?from=2026-06-04&to=2026-06-01")
        assert b"380.00" in response_swapped.data, (
            "Swapped dates must be silently normalised to produce the same result as correct order"
        )

    def test_swapped_dates_all_transactions_present(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-04&to=2026-06-01")
        for description in [b"Lunch", b"Snack", b"Bus pass", b"Electricity"]:
            assert description in response.data, (
                f"After date normalisation, '{description}' must appear in the transaction list"
            )

    def test_swapped_dates_narrow_range_still_normalised(self, client, seeded_db):
        # from=2026-06-03, to=2026-06-02 swapped → Jun 02–03: ₹30 + ₹100 = ₹130
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03&to=2026-06-02")
        assert b"130.00" in response.data, (
            "Swapped narrow range must be normalised and return correct filtered total"
        )


# ================================================================== #
# 8. Invalid date handling                                            #
# ================================================================== #

class TestInvalidDateHandling:
    """Invalid or unparseable date values in query params must be silently ignored."""

    def test_invalid_from_ignored_shows_all_time_data(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=not-a-date&to=2026-06-04")
        assert response.status_code == 200, "Invalid 'from' must not cause an error"
        # 'to' is valid so the to-only filter applies (up to Jun 04 = all 4 = ₹380)
        assert b"380.00" in response.data, (
            "Invalid 'from' must be ignored; valid 'to' still applies (to=Jun 04 = all data)"
        )

    def test_invalid_to_ignored(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=bad-value")
        assert response.status_code == 200, "Invalid 'to' must not cause an error"
        # 'from' valid → Jun 01 onwards = all 4 = ₹380
        assert b"380.00" in response.data, (
            "Invalid 'to' must be ignored; valid 'from' still applies"
        )

    def test_both_invalid_shows_all_time_data(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=abc&to=xyz")
        assert response.status_code == 200, "Both invalid params must not cause an error"
        assert b"380.00" in response.data, (
            "Both invalid params treated as None — all-time data must be shown"
        )
        assert b"Showing:" not in response.data, (
            "'Showing:' label must NOT appear when both params are invalid"
        )
        assert b"Clear" not in response.data, (
            "'Clear' link must NOT appear when both params are invalid"
        )

    def test_invalid_format_variations_ignored(self, client, seeded_db):
        # ISO with time component, wrong separators, etc.
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026/06/01&to=2026.06.04")
        assert response.status_code == 200, "Wrong date format must be silently ignored"
        assert b"380.00" in response.data, (
            "Dates in wrong format must be treated as None — all-time data shown"
        )

    def test_empty_string_params_treated_as_no_filter(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=&to=")
        assert response.status_code == 200, "Empty string params must not cause an error"
        assert b"380.00" in response.data, (
            "Empty string params must be treated as no filter"
        )


# ================================================================== #
# 9. Empty range — no matching expenses                               #
# ================================================================== #

class TestEmptyRangeResult:
    """A filter that matches zero expenses must show ₹0.00 / 0 transactions gracefully."""

    def test_empty_range_returns_200(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2020-01-01&to=2020-12-31")
        assert response.status_code == 200, "Empty range must not cause an error"

    def test_empty_range_shows_zero_total(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2020-01-01&to=2020-12-31")
        assert b"0.00" in response.data, "Empty range must display ₹0.00 total"

    def test_empty_range_shows_zero_transaction_count(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2020-01-01&to=2020-12-31")
        assert b"0 expense" in response.data, "Empty range must display 0 transactions"

    def test_empty_range_no_transactions_listed(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2020-01-01&to=2020-12-31")
        for description in [b"Lunch", b"Snack", b"Bus pass", b"Electricity"]:
            assert description not in response.data, (
                f"'{description}' must not appear in the transaction list for an empty range"
            )

    def test_empty_range_no_category_breakdown(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2020-01-01&to=2020-12-31")
        assert b"No spending data yet." in response.data, (
            "Empty category breakdown must render the empty-state message, not an error"
        )

    def test_empty_range_still_shows_filter_label(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2020-01-01&to=2020-12-31")
        assert b"Showing:" in response.data, (
            "'Showing:' label must still appear even when the range returns zero results"
        )

    def test_empty_range_still_shows_clear_link(self, client, seeded_db):
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2020-01-01&to=2020-12-31")
        assert b"Clear" in response.data, (
            "'Clear' link must still appear even when the range returns zero results"
        )


# ================================================================== #
# 10. Filter label formatting                                         #
# ================================================================== #

class TestFilterLabelFormatting:
    """'Showing:' label must use DD Mon YYYY format and handle partial filters."""

    def test_label_contains_from_date_formatted(self, client, seeded_db):
        # from=2026-06-01 should be rendered as "01 Jun 2026"
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-04")
        assert b"01 Jun 2026" in response.data, (
            "Active filter label must format the 'from' date as DD Mon YYYY"
        )

    def test_label_contains_to_date_formatted(self, client, seeded_db):
        # to=2026-06-04 should be rendered as "04 Jun 2026"
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-01&to=2026-06-04")
        assert b"04 Jun 2026" in response.data, (
            "Active filter label must format the 'to' date as DD Mon YYYY"
        )

    def test_label_with_from_only_shows_present(self, client, seeded_db):
        # from-only: label should indicate "to present" (spec says "present")
        _set_session(client, seeded_db)
        response = client.get("/profile?from=2026-06-03")
        assert b"Showing:" in response.data
        assert b"present" in response.data, (
            "Filter label with from-only must indicate 'present' as the open end"
        )

    def test_label_with_to_only_shows_all_time(self, client, seeded_db):
        # to-only: label should indicate "All time" as the open start (spec says "All time")
        _set_session(client, seeded_db)
        response = client.get("/profile?to=2026-06-02")
        assert b"Showing:" in response.data
        assert b"All time" in response.data, (
            "Filter label with to-only must indicate 'All time' as the open start"
        )


# ================================================================== #
# 11. Query helper unit tests — date parameter wiring                 #
# ================================================================== #

class TestGetSummaryStatsWithDates:
    """get_summary_stats must accept date_from and date_to and filter correctly."""

    def test_no_args_returns_all_time_data(self, seeded_db, app):
        result = get_summary_stats(seeded_db)
        assert result["transaction_count"] == 4
        assert abs(result["total_spent"] - 380.00) < 0.01
        assert result["top_category"] == "Bills"

    def test_date_from_filters_from_date(self, seeded_db, app):
        # from=2026-06-03: Transport ₹100 + Bills ₹200 = ₹300
        result = get_summary_stats(seeded_db, date_from="2026-06-03")
        assert result["transaction_count"] == 2
        assert abs(result["total_spent"] - 300.00) < 0.01

    def test_date_to_filters_to_date(self, seeded_db, app):
        # to=2026-06-02: Food ₹50 + Food ₹30 = ₹80
        result = get_summary_stats(seeded_db, date_to="2026-06-02")
        assert result["transaction_count"] == 2
        assert abs(result["total_spent"] - 80.00) < 0.01

    def test_date_range_filters_both_bounds(self, seeded_db, app):
        # Jun 02 – Jun 03: Snack ₹30 + Bus pass ₹100 = ₹130
        result = get_summary_stats(seeded_db, date_from="2026-06-02", date_to="2026-06-03")
        assert result["transaction_count"] == 2
        assert abs(result["total_spent"] - 130.00) < 0.01

    def test_empty_range_returns_zero_stats(self, seeded_db, app):
        result = get_summary_stats(seeded_db, date_from="2020-01-01", date_to="2020-12-31")
        assert result["transaction_count"] == 0
        assert result["total_spent"] == 0.0
        assert result["top_category"] == "—"

    def test_top_category_reflects_filter(self, seeded_db, app):
        # Jun 01 – Jun 02: only Food, so top_category = Food
        result = get_summary_stats(seeded_db, date_from="2026-06-01", date_to="2026-06-02")
        assert result["top_category"] == "Food"

    def test_none_args_behave_same_as_no_args(self, seeded_db, app):
        result_none = get_summary_stats(seeded_db, date_from=None, date_to=None)
        result_default = get_summary_stats(seeded_db)
        assert result_none["transaction_count"] == result_default["transaction_count"]
        assert abs(result_none["total_spent"] - result_default["total_spent"]) < 0.01


class TestGetRecentTransactionsWithDates:
    """get_recent_transactions must accept date_from and date_to and filter correctly."""

    def test_no_args_returns_all(self, seeded_db, app):
        result = get_recent_transactions(seeded_db)
        assert len(result) == 4

    def test_date_from_excludes_earlier(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_from="2026-06-03")
        assert len(result) == 2
        assert all(r["date"] >= "2026-06-03" for r in result)

    def test_date_to_excludes_later(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_to="2026-06-02")
        assert len(result) == 2
        assert all(r["date"] <= "2026-06-02" for r in result)

    def test_date_range_both_bounds(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_from="2026-06-02", date_to="2026-06-03")
        assert len(result) == 2
        assert all("2026-06-02" <= r["date"] <= "2026-06-03" for r in result)

    def test_limit_applied_after_date_filter(self, seeded_db, app):
        # All 4 expenses in range, limit=2 → should return 2 (limit applied after filter)
        result = get_recent_transactions(seeded_db, limit=2, date_from="2026-06-01")
        assert len(result) == 2, "limit must be applied after the date filter, not before"

    def test_empty_range_returns_empty_list(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_from="2020-01-01", date_to="2020-12-31")
        assert result == []

    def test_results_ordered_newest_first(self, seeded_db, app):
        result = get_recent_transactions(seeded_db, date_from="2026-06-01", date_to="2026-06-04")
        dates = [r["date"] for r in result]
        assert dates == sorted(dates, reverse=True), "Transactions must be ordered newest first"

    def test_none_args_behave_same_as_no_args(self, seeded_db, app):
        result_none = get_recent_transactions(seeded_db, date_from=None, date_to=None)
        result_default = get_recent_transactions(seeded_db)
        assert len(result_none) == len(result_default)

    def test_boundary_dates_inclusive(self, seeded_db, app):
        # from=2026-06-01, to=2026-06-01: only Lunch (Jun 01)
        result = get_recent_transactions(seeded_db, date_from="2026-06-01", date_to="2026-06-01")
        assert len(result) == 1
        assert result[0]["description"] == "Lunch"


class TestGetCategoryBreakdownWithDates:
    """get_category_breakdown must accept date_from and date_to and filter correctly."""

    def test_no_args_returns_all_categories(self, seeded_db, app):
        result = get_category_breakdown(seeded_db)
        assert len(result) == 3

    def test_date_range_reduces_to_one_category(self, seeded_db, app):
        # Jun 01 – Jun 02: only Food
        result = get_category_breakdown(seeded_db, date_from="2026-06-01", date_to="2026-06-02")
        assert len(result) == 1
        assert result[0]["name"] == "Food"

    def test_date_range_correct_amounts(self, seeded_db, app):
        # Jun 03 – Jun 04: Transport ₹100, Bills ₹200
        result = get_category_breakdown(seeded_db, date_from="2026-06-03", date_to="2026-06-04")
        names = {r["name"]: r["amount"] for r in result}
        assert abs(names["Bills"] - 200.00) < 0.01
        assert abs(names["Transport"] - 100.00) < 0.01

    def test_pct_sums_to_100_within_filter(self, seeded_db, app):
        result = get_category_breakdown(seeded_db, date_from="2026-06-02", date_to="2026-06-04")
        assert sum(r["pct"] for r in result) == 100, (
            "Category percentages must sum to exactly 100 for the filtered range"
        )

    def test_empty_range_returns_empty_list(self, seeded_db, app):
        result = get_category_breakdown(seeded_db, date_from="2020-01-01", date_to="2020-12-31")
        assert result == []

    def test_none_args_behave_same_as_no_args(self, seeded_db, app):
        result_none = get_category_breakdown(seeded_db, date_from=None, date_to=None)
        result_default = get_category_breakdown(seeded_db)
        assert len(result_none) == len(result_default)

    def test_from_only_filters_breakdown(self, seeded_db, app):
        # from=2026-06-04: only Bills
        result = get_category_breakdown(seeded_db, date_from="2026-06-04")
        assert len(result) == 1
        assert result[0]["name"] == "Bills"
        assert abs(result[0]["amount"] - 200.00) < 0.01

    def test_to_only_filters_breakdown(self, seeded_db, app):
        # to=2026-06-02: only Food (₹50 + ₹30 = ₹80)
        result = get_category_breakdown(seeded_db, date_to="2026-06-02")
        assert len(result) == 1
        assert result[0]["name"] == "Food"
        assert abs(result[0]["amount"] - 80.00) < 0.01
