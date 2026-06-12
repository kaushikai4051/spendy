# Spec: Delete Expense

## Overview
This step wires up the delete expense feature so users can permanently remove an expense from their account. A delete button appears next to each expense row on the profile page. Clicking it submits a POST form to `/expenses/<id>/delete`, which verifies ownership, removes the row from the database, and redirects back to the profile page. This completes the full CRUD cycle for expenses in Spendly.

## Depends on
- Step 01: Database setup (expenses table)
- Step 04/05: Profile page with expense list rendered
- Step 07: Add expense (expenses exist to delete)
- Step 08: Edit expense (edit button pattern to follow for delete button placement)

## Routes
- `POST /expenses/<int:id>/delete` — delete an expense by ID — logged-in only

## Database changes
No new tables or columns. A new helper function `delete_expense` must be added to `database/db.py`:
- Deletes the row from `expenses` WHERE `id = ?` AND `user_id = ?` (ownership check built into the query)

## Templates
- **Modify:** `templates/profile.html` — add a delete button (HTML form with `method="POST"`) next to each expense row in the recent transactions list, alongside the existing edit button

## Files to change
- `app.py` — replace the placeholder `delete_expense` route with a real implementation
- `database/db.py` — add `delete_expense(expense_id, user_id)` function
- `templates/profile.html` — add delete button/form to each expense row

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never interpolate IDs into SQL strings
- The DELETE query must include `AND user_id = ?` so users cannot delete other users' expenses
- The route must only accept POST (use `methods=["POST"]`); a GET to this URL should return 405
- After a successful delete, redirect to `url_for("profile")`
- If the expense does not exist or belongs to another user, silently redirect to profile (no error needed — idempotent behaviour)
- The delete button must be wrapped in a `<form method="POST">` — no JavaScript required
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Import `delete_expense` from `database.db` in `app.py`

## Definition of done
- [ ] A delete button is visible next to each expense row on `/profile`
- [ ] Clicking delete removes the expense and redirects to `/profile`
- [ ] The deleted expense no longer appears in the list after redirect
- [ ] Attempting to delete another user's expense does nothing (redirect to profile, row untouched)
- [ ] Sending a GET request to `/expenses/<id>/delete` returns 405 Method Not Allowed
- [ ] `delete_expense(expense_id, user_id)` function exists in `database/db.py` and is imported in `app.py`
