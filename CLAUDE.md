# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate the virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the development server (port 5001)
python app.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_auth.py

# Run a single test by name
pytest tests/test_auth.py::test_login_success
```

## Architecture

This is a **Flask expense tracker** called **Spendly**, structured as a teaching project where students implement features step-by-step.

### Request flow

```
Browser → app.py (route) → render_template() → templates/*.html (Jinja2) → base.html layout
```

All routes are in `app.py`. There is no blueprint or module split — one file holds all routes. The database layer lives in `database/db.py` (currently a placeholder).

### Templates

- `templates/base.html` — master layout: navbar, footer, Google Fonts, `static/css/style.css`, `static/js/main.js`. All pages extend this.
- Page templates use `{% block content %}`, `{% block title %}`, `{% block head %}` (extra CSS), and `{% block scripts %}` (extra JS).
- Auth pages (`register.html`, `login.html`) render an `{{ error }}` variable injected by the route when validation fails.

### Static assets

- `static/css/style.css` — global styles with CSS custom properties (`--ink`, `--paper`, `--accent`, etc.). No CSS framework.
- Per-page CSS is loaded via `{% block head %}` (e.g., `landing.css`).
- `static/js/main.js` — global JS. Page-specific JS goes in `{% block scripts %}` as an inline `<script>`.

### Database (not yet implemented)

`database/db.py` will export three functions students must write:
- `get_db()` — returns a SQLite connection with `row_factory` and foreign keys enabled
- `init_db()` — creates all tables with `CREATE TABLE IF NOT EXISTS`
- `seed_db()` — inserts sample development data

### Planned routes (placeholder strings today)

| Route | Function | Step |
|---|---|---|
| `GET/POST /logout` | `logout` | Step 3 |
| `GET /profile` | `profile` | Step 4 |
| `GET/POST /expenses/add` | `add_expense` | Step 7 |
| `GET/POST /expenses/<id>/edit` | `edit_expense` | Step 8 |
| `POST /expenses/<id>/delete` | `delete_expense` | Step 9 |
