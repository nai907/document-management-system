# Document Management System

A Django + Vue app for tracking where documents live, who has viewed/edited/approved/
acknowledged them, and a full audit history — built to replace an ad hoc file-share setup.

## What it solves

- **"We don't know where documents are"** — every document lives in a browsable folder tree
  and is searchable by title, description, tags, or its unique code.
- **"We don't know who acknowledged them"** — documents can be marked as requiring
  acknowledgement; the detail page shows exactly who has (and hasn't) confirmed they read it.
- **"We can't search them"** — full-text-ish search (`?q=`) across title/description/tags/code.
- **"No history check"** — every upload, view, download, edit, permission change, review
  decision, and acknowledgement is written to an audit log, visible per-document and globally
  (admin).
- **"Names may be duplicated"** — every document gets a permanent unique code
  (`DOC-2026-000123`); uploading a title that already exists shows a non-blocking warning
  listing the existing matches.
- **"Reviews stall with no follow-up"** — a simple Draft → In Review → Approved/Rejected
  workflow with assigned reviewers; the admin dashboard flags reviews pending more than 5 days.
- **"No clear view/edit/approve/download permissions"** — global roles (Admin/Employee) plus
  per-document grants scoped to a user or group, each with its own view/edit/approve/download
  flags and an optional expiry date.
- **"No admin dashboard"** — `/admin/dashboard` shows document counts by status, overdue
  reviews, permissions expiring soon, documents missing required acknowledgement, and recent
  activity; `/admin/audit` is the full filterable log.

## Stack

- **Backend**: Django 6 + Django REST Framework, SQLite, JWT auth (`djangorestframework-simplejwt`).
- **Frontend**: Vue 3 (`<script setup>`) + Vite + Vue Router + Pinia + Axios, plain CSS.

No Docker, Postgres, or external search/storage service is required for this version —
everything runs locally with two dev servers.

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

| username | password      | role     | department |
|----------|---------------|----------|------------|
| admin    | admin12345    | admin    | IT         |
| employee | employee12345 | employee | Sales      |

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

## Notable design decisions

- **Permission resolution** (`backend/documents/permissions.py`): admins always pass; a
  document's owner can view/edit/download but not approve their own document; everyone else
  needs an explicit, non-expired `DocumentPermission` grant (direct or via a Django group).
- **Document code** is assigned once on creation and never reused, so it stays a stable
  identifier even if two documents share a title.
- **Audit log** entries are written explicitly inside each mutating view (not via signals),
  so every entry reliably captures the acting user and action-specific metadata.
- **Auth tokens**: the JWT access token is kept in memory only (never persisted); the refresh
  token is kept in `sessionStorage` so a page reload doesn't force a re-login, but it's
  cleared when the tab closes.
- **Search** uses SQLite `icontains` lookups (no Postgres full-text search available on
  SQLite) — sufficient for small/medium document sets; swapping in Postgres + `SearchVector`
  later is a drop-in change to `DocumentListCreateView.get_queryset`.
