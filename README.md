# Zendesk — Internal IT Support Ticket System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/database-SQLite-003B57.svg?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Accessibility WCAG 2.1 AA](https://img.shields.io/badge/accessibility-WCAG%202.1%20AA-0052CC.svg?style=flat)](https://www.w3.org/WAI/standards-guidelines/wcag/)
[![GitHub Copilot](https://img.shields.io/badge/accelerated%20by-GitHub%20Copilot%20(GHCP)-8957E5.svg?style=flat&logo=githubcopilot&logoColor=white)](https://github.com/features/copilot)
[![Dev Days](https://img.shields.io/badge/event-Dev%20Days-FF5722.svg?style=flat)](https://github.com/)

A streamlined, local-first internal IT support ticket queue designed for employees reporting technical issues and IT support teams triaging and resolving them. Built with a modern vanilla web interface, high-performance FastAPI backend, and SQLite persistence with live telemetry and audit logging.

---

## 🌟 Dev Days Showcase & GitHub Copilot (GHCP)

This project was built and accelerated during **Dev Days**, highlighting modern AI-assisted engineering practices powered by **GitHub Copilot (GHCP)**.

- **GitHub Copilot (GHCP) Pair Programming**: Accelerated backend endpoint construction, Pydantic data modeling, and robust test case generation.
- **Repository-Informed Instructions**: Guided by [`.github/copilot-instructions.md`](.github/copilot-instructions.md), which defines strict domain rules, accessibility guidelines, backward-compatibility contracts, and honest telemetry standards.
- **Accessibility by Design**: Leveraged GitHub Copilot to architect multi-modal WCAG 2.1 AA compliant cues (text labels, geometric SVG shapes, 2px structural borders, and screen-reader ARIA live announcements).
- **Zero-Bloat Philosophy**: Maintained a clean architecture using semantic HTML5, modern CSS3, vanilla JavaScript, and lightweight Python ASGI dependencies without extraneous framework baggage.

---

## 🎯 Key Features

- **Intuitive Ticket Intake & Triage**:
  - Quickly file tickets with title, requester, category, priority, and detailed description.
  - Lifecycle state machine: `Open` &rarr; `In Progress` &rarr; `Resolved`.
- **SLA Management & Priority Matrix**:
  - Built-in SLA target tracking by priority:
    - **Critical**: 60 minutes
    - **High**: 240 minutes (4 hours)
    - **Medium**: 1,440 minutes (24 hours)
    - **Low**: 4,320 minutes (72 hours)
  - Automatic timestamp tracking for initial response (transition to `In Progress`) and resolution (transition to `Resolved`).
- **Quad-Layer WCAG 2.1 AA Priority Indicators**:
  - High and Critical priority tickets never rely on color alone. Each uses:
    1. Explicit text labels (`CRITICAL` or `HIGH PRIORITY`).
    2. Distinct geometric SVG icons (`aria-hidden="true"`).
    3. Distinct 2px high-contrast structural borders and surface treatment.
    4. Programmatic screen-reader cues via ARIA attributes.
- **Real-Time SQL Telemetry & Metrics**:
  - Real calculations derived directly from SQLite timestamps: median first response time, SLA compliance percentage, and monthly resolution totals.
  - Metric provenance honesty: displays `null` / `—` when insufficient data exists rather than inventing metrics; clearly demarcates illustrative demo records.
- **Immutable Audit Logging**:
  - Atomic transactions log all actions (`TICKET_CREATED`, `STATUS_CHANGED`, `PRIORITY_CHANGED`, `TICKET_DELETED`, `LEGACY_TICKET_IMPORTED`) with previous/new values and ISO timestamps.
- **Lossless Browser Migration**:
  - Backward-compatible import endpoint (`/api/tickets/import-legacy`) that idempotently imports legacy browser `localStorage` tickets into SQLite without data loss.
- **System Health Monitoring**:
  - Real database and process health telemetry (`/api/health`) reporting live connection status, uptime in seconds, and memory working set usage.
- **Hardened Local Security**:
  - Restrictive Content Security Policy (`CSP`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Cache-Control: no-store` headers.

---

## 🏗️ Architecture & Project Structure

```
Zendesk/
├── .github/
│   └── copilot-instructions.md   # GitHub Copilot (GHCP) project rules & conventions
├── tests/
│   └── test_server.py           # Comprehensive unittest suite for API & database
├── app.js                       # Vanilla JavaScript client logic & DOM management
├── favicon.svg                  # Zendesk branded SVG favicon
├── index.html                   # Semantic HTML5 accessible frontend
├── PRODUCT.md                   # Product specification & UX guidelines
├── README.md                    # Project documentation
├── requirements.txt             # Python runtime dependencies
├── seed_demo.py                 # Idempotent demo dataset generator
├── server.py                    # FastAPI application, SQLite DAL & endpoints
└── styles.css                   # Modern CSS3 design tokens & responsive layout
```

---

## ⚡ Quick Start

### Prerequisites
- **Python 3.10** or higher
- A modern web browser (Edge, Chrome, Firefox, Safari)

### 1. Clone & Set Up Virtual Environment

**On Windows (PowerShell):**
```powershell
git clone https://github.com/roshankodi/Zendesk.git
cd Zendesk

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**On macOS / Linux (bash/zsh):**
```bash
git clone https://github.com/roshankodi/Zendesk.git
cd Zendesk

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Run the Development Server

Start FastAPI with hot reload:
```powershell
python -m uvicorn server:app --reload
```

The application will be live at:
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

> [!NOTE]
> The SQLite database file is automatically created as `tickets.sqlite3` in the project root on first start. You can customize the database path by setting the `TICKET_DB_PATH` environment variable.

### 3. (Optional) Seed Illustrative Demo Data

Populate the database with a pre-configured sample ticket queue to test filtering, SLA calculations, and triage flows:

```powershell
python seed_demo.py
```

> [!TIP]
> Seeded records are explicitly tagged as demo records (`is_demo = 1`). In compliance with product honesty guidelines, the UI visibly marks KPI telemetry as illustrative when demo data is present.

---

## 🔌 API Reference

All API responses use JSON and include restrictive security and `no-store` cache headers.

### Health & Metrics

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service uptime, memory usage, and SQLite connectivity check. |
| `GET` | `/api/metrics` | SQL-calculated telemetry: median first response, SLA compliance rate, resolutions this month, and demo data presence flag. |

#### Example Health Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "uptime_seconds": 124.5,
  "memory_usage_bytes": 31457280,
  "timestamp": "2026-10-10T05:36:42Z"
}
```

### Ticket Management

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/tickets` | List tickets with optional query filters: `?priority=High&status=Open&search=wifi`. |
| `GET` | `/api/tickets/{reference}` | Get single ticket details and complete audit history by reference (`TICK-0001` or legacy ID). |
| `POST` | `/api/tickets` | Create a new ticket (Status defaults to `Open`). |
| `PATCH` | `/api/tickets/{reference}` | Update ticket `status` (`Open`, `In Progress`, `Resolved`) and/or `priority`. |
| `DELETE` | `/api/tickets/{reference}` | Soft-delete a ticket while permanently retaining audit log entries. |
| `POST` | `/api/tickets/import-legacy` | Idempotently import legacy browser `localStorage` tickets into SQLite. |

#### Create Ticket Request Body (`POST /api/tickets`):
```json
{
  "title": "Cannot connect to VPN",
  "requester": "Alex Morgan",
  "category": "Network",
  "priority": "High",
  "description": "VPN connection drops every 5 minutes during client calls."
}
```

#### Update Ticket Request Body (`PATCH /api/tickets/TICK-0001`):
```json
{
  "status": "In Progress",
  "priority": "Critical"
}
```

---

## 🧪 Testing & Verification

Run the automated test suite covering database transactions, API contract validation, metric aggregation, audit logs, and security headers:

```powershell
python -m unittest discover -s tests -v
```

Tests execute against an isolated temporary SQLite database and do not touch local application records.

If Node.js is installed in your environment, validate JavaScript syntax with:
```powershell
node --check .\app.js
```

---

## 🛡️ Security Boundary & Production Notice

- **Authentication**: This application is intentionally built without an authentication layer for lightweight local or single-tenant trusted use.
- **Network Isolation**: By default, bind only to `127.0.0.1`. Do not expose directly to an untrusted public network or the internet without a reverse proxy (e.g., Nginx, Caddy) providing TLS/HTTPS, authentication, rate limiting, and access control.
- **Integrity**: Parameterized SQL queries and strict Pydantic models protect against SQL injection and malformed input.

---

## 🤝 Contributing & Copilot Guidelines

Contributions are welcome! When developing with AI coding assistants such as **GitHub Copilot (GHCP)**, please adhere to [`.github/copilot-instructions.md`](.github/copilot-instructions.md):
- Keep frontend vanilla (no added frameworks or unnecessary build tooling).
- Preserve backward-compatibility for database schemas and API response contracts.
- Strictly uphold WCAG 2.1 AA multi-modal accessibility cues.
- Maintain transparent product truth and data integrity.

---

## 📄 License

Open-source under the [MIT License](LICENSE) (or organizational internal standard).
Developed with 💙 during **Dev Days** with **GitHub Copilot (GHCP)**.
