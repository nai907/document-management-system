# Document Management System

A Django + Vue app for tracking where documents live, who can view/edit/approve/download them,
and a full audit history — built to replace an ad hoc file-share setup.

## What it solves

- **"We don't know where documents are"** — every document lives in a browsable folder tree
  and is searchable by title, description, tags, or its unique code.
- **"We can't search them"** — full-text-ish search (`?q=`) across title/description/tags/code.
- **"No history check"** — every upload, view, download, edit, permission change, and review
  decision is written to an audit log, visible per-document and globally (admin).
- **"Names may be duplicated"** — every document gets a permanent unique code
  (`DOC-2026-000123`), and titles are hard-blocked from duplicating another document's title
  once both are cleaned (trimmed + lowercased) — enforced by a real database unique constraint,
  not just a warning.
- **"Reviews stall with no follow-up"** — a simple Draft → In Review → Approved/Rejected
  workflow with assigned reviewers; the admin dashboard flags reviews pending more than 5 days.
- **"No clear view/edit/approve/download permissions"** — global roles (Admin/Employee) plus
  per-document grants scoped to a user or group, each with its own view/edit/approve/download
  flags and an optional expiry date. Only admins can revoke a grant; owners can only create one.
- **"No admin dashboard"** — `/admin/dashboard` shows document counts by status, who's still
  blocking every in-review document, permissions expiring soon, and recent activity;
  `/admin/audit` is the full filterable log.

## Stack

- **Backend**: Django 6 + Django REST Framework, JWT auth (`djangorestframework-simplejwt`).
  SQLite + local disk by default; Postgres + S3-compatible cloud storage when configured (see
  **Cloud database & storage** below).
- **Frontend**: Vue 3 (`<script setup>`) + Vite + Vue Router + Pinia + Axios, plain CSS.

No Docker or cloud account is required to run this locally — everything works out of the box
with two dev servers and no external service.

## Running it

### Backend (Django API — port 8000)

```
python -m venv backend_venv
backend_venv\Scripts\pip install -r backend\requirements.txt
cd backend
..\backend_venv\Scripts\python.exe manage.py migrate
..\backend_venv\Scripts\python.exe manage.py seed_demo   # optional demo users/documents
..\backend_venv\Scripts\python.exe manage.py runserver 8000
```

`seed_demo` creates 2 accounts (one admin, one employee), plus 13 documents spread across 5
folders (draft/in-review/approved/rejected, some multi-version, an overdue review, an
expiring permission grant, and an intentional duplicate title) so the app has something
realistic to click through immediately. Documents alternate ownership between the two
accounts so the review and permission-grant features have someone to act on the other's
behalf:

| username | role     | department |
|----------|----------|------------|
| admin    | admin    | IT         |
| employee | employee | Sales      |

The passwords aren't listed here (this repo is public and the app may be deployed) — the
`seed_demo` command prints each account's credentials to the console as it creates them.

Run the backend test suite with:

```
..\backend_venv\Scripts\python.exe manage.py test
```

### Frontend (Vue app — port 5173)

```
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` and `/media` to
`http://127.0.0.1:8000`, so both servers must be running.

## Cloud database & storage (optional)

By default the app uses local SQLite and local disk — nothing to configure. To move to a
cloud Postgres database and S3-compatible cloud file storage (e.g. Supabase, which offers
both from one account):

1. `cd backend`, copy `.env.example` to `.env`.
2. Fill in `DATABASE_URL` with your Postgres connection string, and the `AWS_*` variables with
   your storage bucket's S3-compatible credentials and endpoint (see the comments in
   `.env.example` for where to find these in a Supabase project).
3. Re-run migrations against the new database: `..\backend_venv\Scripts\python.exe manage.py migrate`
   (and `seed_demo` again if you want the demo data there too).
4. Restart the backend. `manage.py check` will confirm the settings load correctly even before
   you point it at real credentials.

Leaving a variable unset keeps that piece local — you can move the database to the cloud
before the file storage, or vice versa, independently. **Keep the storage bucket private**
(not public-read): `DocumentDownloadView` fetches file bytes server-side with your credentials
and streams them through the existing permission check, so nothing needs a public URL, and a
public bucket would let anyone with a file's path download it directly, bypassing permissions
entirely.

## Backup & restore

An admin can download a full backup (every database record plus every uploaded file, as one
`.zip`) from **Backup** in the app, and restore from one the same way — restoring fully replaces
whatever's currently in the system, so it asks for a typed confirmation first.

Besides the manual "Download backup" button, backups can run on a schedule two ways:

**In-process timer (on by default).** Whenever `manage.py runserver` is up, a background thread
writes a backup every `BACKUP_INTERVAL_SECONDS` (default `86400`, i.e. daily) and prunes down to
`BACKUP_RETENTION`. Set `BACKUP_INTERVAL_SECONDS=0` to turn it off. This only covers a single
process — it's the right fit for the dev server, but a multi-worker production server (several
gunicorn workers, say) would start one independent timer per worker and write duplicate backups.
For that case, use the OS-level scheduler below instead.

**OS-level scheduler.** Point cron / Windows Task Scheduler at:

```
python manage.py run_backup
```

Both paths write to the same place, controlled by `BACKUP_STORAGE`:

- `local` (default): a timestamped archive in `BACKUP_DIR` (defaults to `backend/backups/`,
  override via the `BACKUP_DIR` env var). Nothing uploads it anywhere — if `BACKUP_DIR` points at
  a synced/cloud-mounted folder, that sync is what gets it off the machine.
- `bucket`: uploaded to the S3 bucket (the same one holding document files) under
  `BACKUP_S3_PREFIX` (default `backups/`). Use this when hosting somewhere with an ephemeral
  disk (Render, Railway, Heroku, ...), where anything written locally is wiped on every redeploy.

Either way it prunes down to the last `BACKUP_RETENTION` backups (default 14, override via
`--retention N` or the `BACKUP_RETENTION` env var).

Example: a nightly backup at 2 AM, keeping the last 30.

- **cron** (Linux/macOS): `0 2 * * * cd /path/to/backend && /path/to/venv/bin/python manage.py run_backup --retention 30`
- **Windows Task Scheduler**: create a task with trigger "Daily at 2:00 AM", action running
  `python.exe` with arguments `manage.py run_backup --retention 30` and "Start in" set to the
  `backend` folder.

## Deploying to Vercel

The repo is set up to deploy as a single Vercel project: the Vue frontend as a static build and
Django as a Python serverless function, with Supabase providing Postgres and file storage
([vercel.json](vercel.json) wires the routing; `backend/vercel_app.py` is the function entrypoint).

1. **Import the repo** at vercel.com → Add New → Project → import
   `document-management-system` from GitHub. Leave Root Directory as the repo root and
   framework preset as "Other" — `vercel.json` drives the whole build.
2. **Set environment variables** (Project → Settings → Environment Variables):
   - `SECRET_KEY` — a fresh random key, e.g. from
     `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
     Do NOT reuse the dev fallback from settings.py; it's public in this repo.
   - `DATABASE_URL` — **must be Supabase's pooler URL, not the direct one.** The direct
     `db.<ref>.supabase.co` host is IPv6-only and unreachable from Vercel functions. In Supabase:
     Connect → "Transaction pooler" URI (port 6543), then paste your DB password into it.
   - `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
     `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME` — same values as local `backend/.env`.
   - `BACKUP_STORAGE=bucket` — Vercel's disk is ephemeral, so scheduled backups go to the bucket.
   - `CRON_SECRET` — any long random string. Vercel automatically sends it as a bearer token
     when its cron (2:00 AM UTC daily, defined in vercel.json) calls `/api/backup/cron/`;
     the endpoint rejects anything else and 404s entirely if this var is unset.
3. **Deploy.** Migrations aren't run by Vercel — run them from your machine against the same
   `DATABASE_URL` (`python manage.py migrate`), which has usually already happened in dev.

Serverless notes: `settings.py` detects `VERCEL=1` and automatically turns off debug (unless
explicitly re-enabled), allows `.vercel.app` hosts, disables the in-process backup timer (a
function has no long-lived process — Vercel Cron replaces it), and stops holding DB connections
across invocations. The Django admin (`/admin/`) isn't routed or styled on Vercel — use it
locally against the same database instead.

## Notable design decisions

- **Permission resolution** (`backend/documents/permissions.py`): admins always pass; a
  document's owner can view/edit/download but not approve their own document; everyone else
  needs an explicit, non-expired `DocumentPermission` grant (direct or via a Django group).
  Only admins can revoke a grant — owners can create one but not take it back.
- **Document code** is assigned once on creation and never reused, so it stays a stable
  identifier even as titles are renamed.
- **Title uniqueness**: `Document.normalized_title` (auto-computed as `title.strip().lower()`
  on every save) carries a real database unique constraint — two documents can never share a
  title, even if they differ only in case or whitespace.
- **Audit log** entries are written explicitly inside each mutating view (not via signals),
  so every entry reliably captures the acting user and action-specific metadata.
- **Auth tokens**: the JWT access token is kept in memory only (never persisted); the refresh
  token is kept in `sessionStorage` so a page reload doesn't force a re-login, but it's
  cleared when the tab closes.
- **Version file URLs are never serialized** (`DocumentVersionSerializer` deliberately omits
  `file`) — exposing a direct file URL there would let anyone with view access reach the file
  regardless of their `can_download` grant. Downloads always go through
  `DocumentDownloadView`, which checks permission first.
- **Search** uses `icontains` lookups against whichever database is configured — sufficient
  for small/medium document sets; swapping in Postgres `SearchVector` for real full-text search
  is a natural next step once the app is actually running on Postgres.
