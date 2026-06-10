# Spec: Add Expense

## Overview
Step 7 replaces the placeholder `GET /expenses/add` route with a fully working
add-expense form. Users who are logged in can record a new expense by entering
an amount, category, date, and optional description. On valid submission the
expense is written to the `expenses` table and the user is redirected to the
dashboard. Validation errors are shown inline without losing the entered data.
This step teaches students how to handle a POST form, validate user input, and
write a parameterised INSERT query — the core CRUD skill the rest of the app
builds on.

## Depends on
- Step 1: Database setup (`expenses` table exists with the correct schema)
- Step 2: Registration (users exist in the database)
- Step 3: Login / Logout (`session["user_id"]` is set on login)

## Routes
- `GET  /expenses/add` — render the blank add-expense form — logged-in only
- `POST /expenses/add` — validate and insert the expense, redirect to dashboard — logged-in only

## Database changes
No database changes. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`
  - Form with `method="POST"` and `action="{{ url_for('add_expense') }}"`
  - Fields:
    - `amount` — number input, step="0.01", min="0.01", required
    - `category` — `<select>` with fixed options: Food, Transport, Bills,
      Health, Entertainment, Shopping, Other
    - `date` — `<input type="date">`, required, defaults to today's date
    - `description` — `<textarea>`, optional, max 200 chars
  - Submit button labelled "Add Expense"
  - "Cancel" link back to the dashboard
  - `{{ error }}` paragraph shown when the route injects a validation message
  - Re-populate all field values from `form_data` on validation failure so the
    user does not have to retype everything

## Files to change
- `app.py` — replace the stub `add_expense()` function with a full
  `GET`/`POST` implementation:
  - `GET`: redirect to login if not authenticated; render `add_expense.html`
    with today's date pre-filled
  - `POST`: validate inputs, INSERT into `expenses`, redirect to `/dashboard`
    on success; re-render the form with `error` and `form_data` on failure

## Files to create
- `templates/add_expense.html` — the add-expense form template (see Templates)
- `static/css/add_expense.css` — page-specific styles loaded via
  `{% block head %}`; use CSS variables, no hardcoded hex values

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Redirect to `url_for("login")` if `session["user_id"]` is not set
- Validate in `app.py` before touching the database:
  - `amount` must be a positive number (> 0); reject non-numeric input
  - `category` must be one of the fixed allowed values (whitelist check)
  - `date` must be a valid `YYYY-MM-DD` string
  - `description` is optional; strip whitespace and store `None` if empty
- On validation failure, re-render the form — do NOT redirect
- On success, redirect to `url_for("dashboard")`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Currency must always display as ₹ — never £ or $
- The `date` field must default to today's date (`datetime.today().strftime("%Y-%m-%d")`)
  on GET so the user rarely needs to change it

## Definition of done
- [ ] `GET /expenses/add` redirects to `/login` when the user is not logged in
- [ ] `GET /expenses/add` renders the form with the date pre-filled to today for a logged-in user
- [ ] All four fields (amount, category, date, description) appear on the form
- [ ] Category `<select>` contains exactly: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- [ ] Submitting a valid form inserts one row in the `expenses` table with the correct `user_id`, `amount`, `category`, `date`, and `description`
- [ ] After successful submission the user is redirected to `/dashboard`
- [ ] Submitting with a missing or zero amount shows a validation error and re-renders the form
- [ ] Submitting with a non-numeric amount shows a validation error and re-renders the form
- [ ] Submitting with an invalid category value shows a validation error (guards against tampering)
- [ ] Submitting with a missing date shows a validation error and re-renders the form
- [ ] On validation failure, previously entered values are preserved in the form fields
- [ ] An empty description is stored as `NULL` in the database (not an empty string)
- [ ] Page renders without console errors and matches the Spendly visual style
