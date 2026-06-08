# Spec: Date Filter Profile

## Overview
Step 6 adds a date range filter to the profile page so users can narrow all
three data panels — summary stats, recent transactions, and category breakdown —
to a specific period. A compact filter bar with "from" and "to" date inputs sits
above the stats cards. The filter is submitted as GET query parameters
(`?from=YYYY-MM-DD&to=YYYY-MM-DD`) so the URL is bookmarkable and the browser
back button works naturally. When no filter is active the page behaves exactly
as it does today (all-time data). This step teaches students how to thread
optional parameters through a route into query helpers without breaking the
existing no-filter path.

## Depends on
- Step 1: Database setup (`expenses` table with `date` column)
- Step 2: Registration (users exist in the database)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page design (template already renders all three data panels)
- Step 5: Backend routes for profile page (`queries.py` helpers exist)

## Routes
No new routes. The existing `GET /profile` route is extended to read optional
`from` and `to` query string parameters.

- `GET /profile` — unfiltered profile (existing behaviour, unchanged)
- `GET /profile?from=YYYY-MM-DD&to=YYYY-MM-DD` — profile filtered to date range (logged-in)
- `GET /profile?from=YYYY-MM-DD` — filter from date to today (logged-in)
- `GET /profile?to=YYYY-MM-DD` — filter from the beginning of time to date (logged-in)

## Database changes
No database changes. The `expenses.date` column (`TEXT`, stored as `YYYY-MM-DD`)
is already present and supports ISO string comparison.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar above the stats cards with two `<input type="date">` fields
    (`name="from"` and `name="to"`) and a "Filter" submit button.
  - Add a "Clear" link (`href="{{ url_for('profile') }}"`) beside the button,
    visible only when a filter is active.
  - Pre-populate input values from the `date_from` and `date_to` template
    variables so the fields retain the active filter after submission.
  - When a filter is active, show a short label above the stats cards such as
    "Showing: 01 Jun 2026 – 08 Jun 2026".

## Files to change
- `app.py` — read and validate `from` / `to` query params in `profile()`; pass
  them to the three query helpers and back to the template as `date_from` and
  `date_to`.
- `database/queries.py` — add optional `date_from: str | None` and
  `date_to: str | None` parameters to `get_summary_stats`,
  `get_recent_transactions`, and `get_category_breakdown`. When either is
  provided, append `AND date >= ?` / `AND date <= ?` clauses to the queries.
- `templates/profile.html` — filter bar UI and active-filter label (see
  Templates section above).

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Validate date strings in `app.py` before passing to queries: accept only
  `YYYY-MM-DD` format; silently ignore values that don't parse (treat as `None`)
- If both `from` and `to` are supplied and `from > to`, swap them silently so
  the query always works
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles — add filter bar styles to `static/css/profile.css`
- Currency must always display as ₹ — never £ or $
- The filter form must use `method="GET"` so the date range appears in the URL
- Existing calls to the three query helpers with no date args must continue to
  work without modification (default `None` parameters)
- `get_recent_transactions` limit (default 10) applies after the date filter,
  not before

## Definition of done
- [ ] Visiting `/profile` with no query params shows all-time data (unchanged behaviour)
- [ ] Entering a from-date and to-date and clicking "Filter" reloads the page with `?from=…&to=…` in the URL
- [ ] Stats cards (total spent, transaction count, top category) reflect only expenses within the filtered date range
- [ ] The transaction list shows only transactions within the filtered date range
- [ ] The category breakdown reflects only expenses within the filtered date range
- [ ] The date inputs are pre-filled with the active filter values after filtering
- [ ] A "Showing: DD Mon YYYY – DD Mon YYYY" label appears above the stats when a filter is active; it is absent when no filter is active
- [ ] A "Clear" link appears beside the Filter button when a filter is active; clicking it returns to the unfiltered view
- [ ] Filtering to a date range with no expenses shows ₹0.00 total, 0 transactions, empty category breakdown — no errors
- [ ] Filtering with only a `from` date (no `to`) returns all expenses from that date to the present
- [ ] Filtering with only a `to` date (no `from`) returns all expenses up to and including that date
- [ ] An invalid date value in the query string (e.g. `?from=abc`) is silently ignored and the page loads as unfiltered
