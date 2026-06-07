# Spec: Profile Page Design

## Overview
Implement the `/profile` route so logged-in users can view and update their account information. The page displays the user's name, email, and member-since date alongside a quick summary of their spending (total expenses and total amount). A form lets the user change their name, email, or password. This is the first authenticated page students build beyond the bare-bones dashboard, so it reinforces the session-guard pattern and parameterised UPDATE queries before the more complex expense CRUD steps begin.

## Depends on
- Step 1 (Database Setup) — `get_db()`, `users` table, and `expenses` table must exist.
- Step 2 (Registration) — `users` rows with `name`, `email`, `password_hash`, `created_at` must be insertable.
- Step 3 (Login and Logout) — session must be set (`session["user_id"]`) before profile can be accessed.

## Routes
- `GET /profile` — fetch the logged-in user's record and expense stats; render `profile.html` — logged-in only
- `POST /profile` — validate and apply name / email / password changes; re-render on error, redirect to `GET /profile` on success — logged-in only

## Database changes
No new tables or columns. Reads from existing `users` and `expenses` tables:
```
users(id, name, email, password_hash, created_at)
expenses(id, user_id, amount, ...)
```

## Templates
- **Create:** `templates/profile.html` — full profile page extending `base.html`; shows user info card, spending summary card, and an edit form
- **Modify:** none

## Files to change
- `app.py` — replace the placeholder `profile` route body with a full GET/POST handler

## Files to create
- `templates/profile.html` — profile page template
- `static/css/profile.css` — page-scoped styles loaded via `{% block head %}`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never string-format SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`; verified with `check_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Both GET and POST must check `session.get("user_id")` and redirect to `/login` if not set
- On POST, re-fetch the current user row before validating so stale form data cannot overwrite fields the user did not touch
- Password change is optional: only hash and update `password_hash` if the "new password" field is non-empty
- If the user submits a new password, require a "current password" field and verify it with `check_password_hash` before accepting the change
- If the requested email is already taken by another account, catch `sqlite3.IntegrityError` and re-render with an error
- After a successful POST, update `session["user_name"]` if the name changed, then redirect to `GET /profile` (PRG pattern)
- Spending summary stats (expense count and total amount) must come from a single SQL query against the `expenses` table filtered by `user_id`
- Display `created_at` formatted as a human-readable date (e.g. "June 2026") — format in Python, not in Jinja2 filters
- The edit form fields must be pre-populated with the current values on GET

## Definition of done
- [ ] `GET /profile` returns 200 and shows the logged-in user's name, email, and member-since date
- [ ] `GET /profile` shows total expense count and total amount spent for the logged-in user
- [ ] `GET /profile` for an unauthenticated visitor redirects to `/login`
- [ ] The edit form is pre-populated with the user's current name and email
- [ ] Submitting the form with a new valid name updates the `users` row and refreshes the page showing the new name
- [ ] The navbar also reflects the new name after a name change (session updated)
- [ ] Submitting a new email that belongs to another account re-renders the form with a friendly error
- [ ] Leaving the password fields blank performs no password change
- [ ] Supplying a wrong current password re-renders the form with an error and does not update the password
- [ ] Supplying a correct current password and a new password (≥ 8 characters) updates `password_hash` in the database
- [ ] Logging out after a profile update and logging back in with the new password succeeds
