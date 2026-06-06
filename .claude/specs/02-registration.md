# Spec: Registration

## Overview
Implement user registration and login so new users can create an account and sign in to Spendly. Registration collects name, email, and password; login verifies credentials and establishes a Flask session. Both routes already exist as GET-only stubs — this step converts them to full GET/POST handlers, wires them to the `users` table, and adds session support to the app. After this step, a user can register, log in, and be redirected to an authenticated area. Logout (Step 3) will end the session.

## Depends on
- Step 1 (Database Setup) — `users` table and `get_db()` must be in place.

## Routes
- `GET/POST /register` — render registration form (GET); validate input, insert user, redirect to `/login` (POST) — public
- `GET/POST /login` — render login form (GET); verify credentials, set session, redirect to `/dashboard` (POST) — public
- `GET /dashboard` — placeholder page shown after successful login — logged-in only

## Database changes
No new tables or columns. Uses existing `users` table:
```
users(id, name, email, password_hash, created_at)
```

## Templates
- **Create:** `templates/dashboard.html` — minimal logged-in landing page showing the user's name and a logout link
- **Modify:** `templates/register.html` — ensure `<form method="POST">` with fields `name`, `email`, `password`, `confirm_password`; render `{{ error }}` when set
- **Modify:** `templates/login.html` — ensure `<form method="POST">` with fields `email`, `password`; render `{{ error }}` when set
- **Modify:** `templates/base.html` — update navbar: show "Dashboard / Logout" links when `session.user_id` is set, show "Register / Login" when not

## Files to change
- `app.py` — add `secret_key`, import `session` and `redirect` and `url_for` from Flask, convert `/register` and `/login` to GET/POST, add `/dashboard` route
- `templates/register.html` — add POST form with correct field names and `{{ error }}` display
- `templates/login.html` — add POST form with correct field names and `{{ error }}` display
- `templates/base.html` — conditional nav links based on session

## Files to create
- `templates/dashboard.html` — basic authenticated home page

## New dependencies
No new dependencies. Uses:
- `werkzeug.security` — `generate_password_hash`, `check_password_hash` (already installed)
- `flask.session` — built-in Flask session (requires `secret_key`)

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never string-format SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`; verified with `check_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set before any session use; use a hard-coded dev string for now (e.g. `"spendly-dev-secret"`)
- Store only `user_id` and `user_name` in the session — never the password hash
- On duplicate email at registration, catch the `sqlite3.IntegrityError` and re-render the form with a friendly error message
- On login failure (wrong email or password), show a generic "Invalid email or password" message — do not reveal which field is wrong
- After successful registration redirect to `/login` with no auto-login
- After successful login redirect to `/dashboard`
- `/dashboard` must check `session.get("user_id")` and redirect to `/login` if not set

## Definition of done
- [ ] `GET /register` renders the registration form
- [ ] Submitting the form with valid data creates a new user row in `users` and redirects to `/login`
- [ ] Submitting with a duplicate email re-renders the form with an error message
- [ ] Submitting with mismatched passwords re-renders the form with an error message
- [ ] Submitting with any blank field re-renders the form with an error message
- [ ] `GET /login` renders the login form
- [ ] Submitting valid credentials sets `session["user_id"]` and redirects to `/dashboard`
- [ ] Submitting wrong credentials re-renders the form with a generic error
- [ ] `GET /dashboard` returns 200 for a logged-in user showing their name
- [ ] `GET /dashboard` redirects to `/login` for an unauthenticated visitor
- [ ] Navbar shows Register/Login links when logged out and Dashboard/Logout links when logged in
- [ ] Password is never stored in plain text — only the hash is in the database
