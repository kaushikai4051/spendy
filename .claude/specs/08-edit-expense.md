# Spec: Edit Expense

## Overview
Step 8 replaces the placeholder `GET /expenses/<id>/edit` stub with a fully
working edit-expense form. A logged-in user can click "Edit" next to any of
their own expenses on the profile page, change one or more fields (amount,
category, date, description), and save. The existing row is updated in-place
with a parameterised `UPDATE` query. Validation rules are identical to Step 7
(Add Expense) so students reinforce input-validation skills while learning
the SELECT → pre-populate → UPDATE pattern. Ownership is enforced: a user
cannot edit another user's expense.

## Depends on
- Step 1: Database setup (`expenses` table exists with the correct schema)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Profile page backend (profile route renders recent transactions)
- Step 7: Add Expense (same validation rules; `EXPENSE_CATEGORIES` constant reused)

## Routes
- `GET  /expenses/<int:id>/edit` — fetch the expense, render pre-populated edit form — logged-in only
- `POST /expenses/<int:id>/edit` — validate and UPDATE the expense row, redirect to profile — logged-in only

## Database changes
No new tables or columns. The existing `expenses` schema covers all fields.

A new helper function must be added to `database/db.py`:
- `get_expense(expense_id: int) -> sqlite3.Row | None` — returns the row for the given id, or `None`
- `update_expense(expense_id: int, user_id: int, amount: float, category: str, date: str, description) -> None` — issues a parameterised `UPDATE expenses SET ... WHERE id = ? AND user_id = ?`

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`
  - Form with `method="POST"` and `action="{{ url_for('edit_expense', id=expense.id) }}"`
  - Fields identical to `add_expense.html`:
    - `amount` — number input, step="0.01", min="0.01", required; pre-filled from `form_data`
    - `category` — `<select>` with the same seven options; pre-selected from `form_data`
    - `date` — `<input type="date">`, required; pre-filled from `form_data`
    - `description` — `<textarea>`, optional; pre-filled from `form_data`
  - Submit button labelled "Save Changes"
  - "Cancel" link back to `/profile`
  - `{{ error }}` paragraph shown when the route injects a validation message
  - On GET, `form_data` is populated from the database row; on POST failure it is populated from `request.form`

- **Modify:** `templates/profile.html`
  - Add an "Edit" link on each row of the recent transactions list:
    `<a href="{{ url_for('edit_expense', id=tx.id) }}">Edit</a>`

## Files to change
- `app.py`
  - Replace the stub `edit_expense()` with a full `GET`/`POST` implementation:
    - Accept `methods=["GET", "POST"]` on the route decorator
    - `GET`: redirect to login if not authenticated; fetch the expense with `get_expense(id)`; return 404 if not found; redirect to `/profile` with no error if the expense belongs to a different user; render `edit_expense.html` with `form_data` pre-populated from the row
    - `POST`: validate inputs (same rules as `add_expense`); on failure re-render the form with `error` and `form_data`; on success call `update_expense(...)` and redirect to `url_for("profile")`
  - Import `get_expense` and `update_expense` from `database.db`

- `database/db.py`
  - Add `get_expense(expense_id: int)` — `SELECT * FROM expenses WHERE id = ?`
  - Add `update_expense(expense_id, user_id, amount, category, date, description)` — `UPDATE expenses SET amount=?, category=?, date=?, description=? WHERE id=? AND user_id=?`

## Files to create
- `templates/edit_expense.html` — edit-expense form template (see Templates)
- `static/css/edit_expense.css` — page-specific styles loaded via `{% block head %}`; use CSS variables, no hardcoded hex values

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Redirect to `url_for("login")` if `session["user_id"]` is not set
- Ownership check: if the fetched expense's `user_id != session["user_id"]`, redirect to `/profile` (do not expose a 403 that leaks expense existence)
- Validate in `app.py` before touching the database:
  - `amount` must be a positive number (> 0); reject non-numeric input
  - `category` must be one of `EXPENSE_CATEGORIES` (whitelist check)
  - `date` must be a valid `YYYY-MM-DD` string via `_parse_date()`
  - `description` is optional; strip whitespace and store `None` if empty
- On validation failure, re-render the form — do NOT redirect
- On success, redirect to `url_for("profile")`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Currency must always display as ₹ — never £ or $

## Definition of done
- [ ] `GET /expenses/<id>/edit` redirects to `/login` when the user is not logged in
- [ ] `GET /expenses/<id>/edit` returns 404 when the expense id does not exist
- [ ] `GET /expenses/<id>/edit` redirects to `/profile` when the expense belongs to a different user
- [ ] `GET /expenses/<id>/edit` renders the form pre-populated with the expense's current values for a logged-in owner
- [ ] All four fields (amount, category, date, description) appear on the form with correct pre-filled values
- [ ] Category `<select>` has the correct option pre-selected
- [ ] Submitting a valid form updates the existing row in `expenses` (no new row is inserted)
- [ ] After successful submission the user is redirected to `/profile`
- [ ] Submitting with a missing or zero amount shows a validation error and re-renders the form
- [ ] Submitting with a non-numeric amount shows a validation error and re-renders the form
- [ ] Submitting with an invalid category shows a validation error
- [ ] Submitting with a missing date shows a validation error and re-renders the form
- [ ] On validation failure, the entered values are preserved in the form fields
- [ ] An empty description is stored as `NULL` in the database (not an empty string)
- [ ] "Edit" links on the profile page's transaction list navigate to the correct edit URL for each expense
- [ ] Page renders without console errors and matches the Spendly visual style
