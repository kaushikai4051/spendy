# Spec: Login and Logout

## Overview
Complete the authentication loop by implementing the `/logout` route, which currently returns a placeholder string. Once this step is done, a user can sign in, browse authenticated pages, and sign out — clearing their session entirely. The login route is already fully implemented from Step 2; this step's only code change is converting the logout stub into a working handler that calls `session.clear()` and redirects to the landing page.

## Depends on
- Step 1 (Database Setup) — `get_db()` and the `users` table must exist.
- Step 2 (Registration) — login route, session wiring, and `dashboard.html` must be in place.

## Routes
- `GET /logout` — clear the Flask session, redirect to `/` — logged-in only (redirect to `/` if already logged out)

## Database changes
No database changes.

## Templates
- **Create:** none
- **Modify:** none — `base.html` already renders the "Sign out" link to `url_for('logout')` conditionally when `session.get('user_id')` is set.

## Files to change
- `app.py` — replace the placeholder `logout` route body with `session.clear()` + `redirect(url_for('landing'))`

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `session.clear()` — not `session.pop()` — to wipe the entire session at once
- After logout, redirect to `url_for('landing')`, not `/login`, so the user lands on the public home page
- Do not require POST for logout — a simple `GET /logout` is sufficient at this stage
- Do not add flash messages — the landing page navbar already reflects the logged-out state

## Definition of done
- [ ] Visiting `/logout` while logged in clears the session and redirects to the landing page (`/`)
- [ ] After logout, the navbar shows "Sign in" and "Get started" links (not "Dashboard" / "Sign out")
- [ ] Visiting `/logout` while already logged out also redirects to `/` without error
- [ ] Visiting `/dashboard` after logout redirects to `/login` (session guard still works)
- [ ] The "Sign out" link in the navbar works from every page that inherits `base.html`
