# Zendesk

A lightweight ticket queue for employees reporting internal IT issues and support staff triaging and resolving them. The browser UI uses semantic HTML, CSS, and vanilla JavaScript; FastAPI and SQLite provide shared persistence and live ticket telemetry.

## Requirements

- Python 3.10 or newer
- A modern browser

## Run locally

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn server:app --reload
```

Open `http://127.0.0.1:8000`. The SQLite database is created as `tickets.sqlite3` in the project directory. Set `TICKET_DB_PATH` to use another database path.

## Deployment and security boundary

This application has no authentication or authorization. Keep it bound to `127.0.0.1` and use it only in a trusted local environment; do not expose it directly to the internet or an untrusted network. A production deployment for multiple users requires an authenticated access layer and HTTPS at a trusted reverse proxy. The app adds restrictive content, framing, referrer, and permissions headers and prevents API responses from being cached, but those controls do not replace authentication, network isolation, HTTPS, backups, or operational monitoring.

For a local non-reloading run, start the same ASGI app without `--reload`:

```powershell
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Install only the runtime packages listed in `requirements.txt`, which defines the supported version ranges. Keep the SQLite database on a persistent, backed-up disk. The API and page are same-origin and require no CORS configuration.

To start the API with illustrative tickets for exploring the queue and filtering:

```powershell
python seed_demo.py
```

Seeded records are explicitly marked as demo content. When demo records are present, the page labels KPI telemetry as illustrative. Do not treat demo-derived metrics as organization performance.

## Features

- Create and search tickets by ID, title, and requester.
- Filter the ticket queue and preview board by priority.
- Change status between Open, In Progress, and Resolved; update priority.
- Delete tickets with confirmation.
- Display SQL-derived status totals, first-response time, SLA compliance, and monthly resolutions when the required data exists.
- Show a server and database health status from a real health check.
- Record ticket creation, status/priority changes, and deletion in the SQLite audit log.
- Import tickets from the former browser-local `mini-it-support-tickets` storage key once records are submitted to the backend. Local data is retained as a backup and not silently deleted.
- Serve a Zendesk-branded SVG favicon and page metadata; use restrictive response headers and no-store caching for API data.

High and critical priority use explicit labels, geometric icons, ARIA text, and distinct 2px structural emphasis. The app keeps the existing three ticket statuses.

## API

- `GET /api/health` — process uptime, database connectivity, and timestamp.
- `GET /api/metrics` — SQL-derived ticket and SLA metrics, plus telemetry provenance.
- `GET /api/tickets?priority=High&status=Open&search=network` — list and filter tickets.
- `GET /api/tickets/{ticket_id}` — retrieve a ticket by its `TICK-...` ID or legacy ID.
- `POST /api/tickets` — create a ticket.
- `POST /api/tickets/import-legacy` — idempotently import legacy browser tickets.
- `PATCH /api/tickets/{ticket_id}` — update status and/or priority.
- `DELETE /api/tickets/{ticket_id}` — soft-delete a ticket while retaining audit history.

New-ticket SLA targets are Critical: 60 minutes, High: 240 minutes, Medium: 1440 minutes, and Low: 4320 minutes. First response is recorded on the first transition to In Progress. A resolution time is recorded on transition to Resolved. SLA compliance uses resolved tickets with recorded timestamps; response-time reporting uses tickets with a recorded first response. When no eligible records exist, the API returns `null` for that metric rather than inventing a value.

## Verification

```powershell
python -m unittest discover -s tests -v
node --check .\app.js
```

The tests use a temporary SQLite database and do not alter the local app database. There is no separate frontend compilation step: the production site consists of the static HTML, CSS, and JavaScript served by FastAPI. Syntax-check JavaScript with Node.js available.
