# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements.txt   # Flask, mysql-connector-python, Werkzeug
python app.py                     # run the dev server (debug=True, http://127.0.0.1:5000)
```

Database setup: import `database/travel_together完整資料庫.sql` into a local MySQL server. The script starts with `DROP DATABASE IF EXISTS` — it is a full rebuild, not an incremental migration, and re-running it wipes and recreates all data (including the seed/test rows at the bottom of the file). Connection settings are in `config.py` (`DB_CONFIG`: host/user/password/database — defaults to `localhost` / `root` / no password / `travel_together`).

There is no test suite, linter, or build step configured in this repo.

Seed accounts (password `123456` for all): `member01` (member), `contentadmin` (content_admin), `admin` (system_admin).

## Architecture

Flask app with raw SQL (no ORM) via `mysql.connector`, and server-rendered Jinja templates (no frontend framework/bundler).

**Three user roles** (`users.role`: `member`, `content_admin`, `system_admin`) each get their own home route and template; `redirect_by_role()` in `app.py` is the single place that maps a role to its landing page after login.

**Two coding eras coexist in this codebase** — be aware of which one you're extending:
- *Original routes* (login/register/member/system-admin/admin_users) live directly in `app.py`, each with its own inline `if "user_id" not in session` / role check, and each opens/closes its own `mysql.connector` connection per request.
- *Content-admin feature* (everything under `/content-admin/...`) is organized as Flask **blueprints** in `blueprints/` (one file per resource: `attractions.py`, `restaurants.py`, `accommodations.py`, `locations.py`, `categories.py`, `proposals.py`, `ai_data.py`, `reports.py`), all registered in `app.py`. These share `db.py` (`get_db_connection()`) and `auth.py` (`@login_required(role="content_admin")` decorator) instead of repeating the session-check boilerplate. `utils.py` holds the image-upload helper (`save_uploaded_image`/`delete_uploaded_image`, saves under `static/uploads/<subfolder>/`) and shared dropdown queries (`get_countries`/`get_cities`/`get_categories`). New content-admin resources should follow this blueprint pattern, not the inline `app.py` pattern.

**Templates** mirror the same split: the original pages (`login.html`, `register.html`, `member_home.html`, `system_admin_home.html`, `admin_users.html`) are each a fully self-contained HTML file with no `{% extends %}`. Everything under `templates/content_admin/` extends `templates/content_admin/base.html` (sidebar + flash-message block), which is the only template inheritance in the project — keep new content-admin pages inside that hierarchy rather than duplicating the shell.

**Data model** (`database/travel_together完整資料庫.sql`) centers on `trips` owned by members, with `itineraries`, `proposals`, `votes`, `comments`, and `expenses` hanging off a trip. `attractions`/`restaurants`/`accommodations` are the shared content catalog (managed by `content_admin`) and are looked up by `country_id`/`city_id` FKs into normalized `countries`/`cities` tables — there are no free-text country/city columns on these three tables. `categories` is a single polymorphic table shared by `trip`/`attraction`/`restaurant`/`accommodation`/`expense` via `category_type`; the content-admin categories blueprint only ever touches the `attraction`/`restaurant`/`accommodation` types. `attractions`/`restaurants`/`accommodations` also carry `ai_verified_at`/`ai_verified_by`, marking when a content admin last confirmed a row's data for the AI itinerary-planning feature. Member-submitted content changes go through `proposals.content_review_status` (`not_required`/`pending`/`approved`/`returned`), reviewed by content admins via the `proposals` blueprint — approving/returning does not itself write into `attractions`/etc.

**Two view helpers used everywhere in `db.py`-style code**: open a connection with `get_db_connection()` (returns `None` on failure — every route must handle that), get a `dictionary=True` cursor for SELECTs, and always `cursor.close()`/`connection.close()` in a `finally` block. Mutations wrap the write in `try/except`, `connection.rollback()` on error, `flash()` a message either way.

**CSS**: single shared stylesheet at `static/css/style.css`, no per-page or component CSS files. Content-admin pages reuse the `admin-*`/`status-*` class vocabulary already established by the system-admin pages (e.g. `status-active`/`status-hidden`/`status-pending` badges, `.admin-table`, `.filter-form`).
