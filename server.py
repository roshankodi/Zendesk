from __future__ import annotations

import os
import sqlite3
import time
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ROOT = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("TICKET_DB_PATH", ROOT / "tickets.sqlite3"))
VALID_CATEGORIES = {"Hardware", "Software", "Network", "Account access", "Other"}
SLA_TARGETS = {"Critical": 60, "High": 240, "Medium": 1440, "Low": 4320}
Priority = Literal["Critical", "High", "Medium", "Low"]
Status = Literal["Open", "In Progress", "Resolved"]
CATEGORY = Literal["Hardware", "Software", "Network", "Account access", "Other"]


class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    requester: str = Field(min_length=1, max_length=80)
    category: CATEGORY
    priority: Priority
    description: str = Field(min_length=1, max_length=1000)

    @field_validator("title", "requester", "description", mode="before")
    @classmethod
    def reject_whitespace_only(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("This field cannot be empty or whitespace only.")
        return value


class TicketUpdate(BaseModel):
    status: Status | None = None
    priority: Priority | None = None

    @model_validator(mode="after")
    def require_an_update(self) -> "TicketUpdate":
        if self.status is None and self.priority is None:
            raise ValueError("Provide a status or priority to update.")
        return self


class LegacyTicket(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=120)
    requester: str = Field(min_length=1, max_length=80)
    category: CATEGORY
    priority: Literal["Low", "Medium", "High", "Critical"]
    status: Status
    description: str = Field(min_length=1, max_length=1000)
    createdAt: datetime

    @field_validator("title", "requester", "description", mode="before")
    @classmethod
    def reject_blank_legacy_fields(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Legacy ticket fields cannot be blank.")
        return value


class LegacyImport(BaseModel):
    tickets: list[LegacyTicket] = Field(max_length=5000)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def process_memory_usage_bytes() -> int | None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = wintypes.HANDLE
        get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        get_memory_info.restype = wintypes.BOOL
        process = get_current_process()
        succeeded = get_memory_info(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        return counters.WorkingSetSize if succeeded else None

    try:
        with open("/proc/self/statm", encoding="ascii") as statm:
            resident_pages = int(statm.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        return None


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(database_path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_number INTEGER PRIMARY KEY AUTOINCREMENT,
                legacy_id TEXT UNIQUE,
                title TEXT NOT NULL,
                requester TEXT NOT NULL,
                category TEXT NOT NULL CHECK (category IN ('Hardware', 'Software', 'Network', 'Account access', 'Other')),
                priority TEXT NOT NULL CHECK (priority IN ('Critical', 'High', 'Medium', 'Low')),
                status TEXT NOT NULL CHECK (status IN ('Open', 'In Progress', 'Resolved')),
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                first_response_at TEXT,
                resolved_at TEXT,
                sla_target_minutes INTEGER NOT NULL,
                assigned_to TEXT,
                is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
                deleted_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
            CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
            CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number INTEGER NOT NULL REFERENCES tickets(ticket_number),
                action TEXT NOT NULL,
                performed_by TEXT NOT NULL,
                previous_value TEXT,
                new_value TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_ticket ON audit_logs(ticket_number, id);
            """
        )
        connection.commit()


def ticket_ref(ticket_number: int) -> str:
    return f"TICK-{ticket_number:04d}"


def row_to_ticket(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": ticket_ref(row["ticket_number"]),
        "title": row["title"],
        "requester": row["requester"],
        "category": row["category"],
        "priority": row["priority"],
        "status": row["status"],
        "description": row["description"],
        "createdAt": row["created_at"],
        "firstResponseAt": row["first_response_at"],
        "resolvedAt": row["resolved_at"],
        "slaTargetMinutes": row["sla_target_minutes"],
        "assignedTo": row["assigned_to"],
        "isDemo": bool(row["is_demo"]),
    }


def get_ticket_row(connection: sqlite3.Connection, reference: str) -> sqlite3.Row | None:
    cleaned = reference.strip().lstrip("#").upper()
    if cleaned.startswith("TICK-") and cleaned[5:].isdigit():
        return connection.execute(
            "SELECT * FROM tickets WHERE ticket_number = ? AND deleted_at IS NULL",
            (int(cleaned[5:]),),
        ).fetchone()
    if cleaned.startswith("REQ-") and len(cleaned) > 4:
        return connection.execute(
            "SELECT * FROM tickets WHERE UPPER(SUBSTR(legacy_id, -6)) = ? AND deleted_at IS NULL",
            (cleaned[-6:],),
        ).fetchone()
    return connection.execute(
        "SELECT * FROM tickets WHERE UPPER(legacy_id) = ? AND deleted_at IS NULL",
        (cleaned,),
    ).fetchone()


def add_audit_entry(
    connection: sqlite3.Connection,
    ticket_number: int,
    action: str,
    previous_value: str | None,
    new_value: str | None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_logs (ticket_number, action, performed_by, previous_value, new_value, created_at)
        VALUES (?, ?, 'Local support user', ?, ?, ?)
        """,
        (ticket_number, action, previous_value, new_value, utc_now()),
    )


def ticket_metrics(connection: sqlite3.Connection) -> dict[str, object]:
    aggregates = connection.execute(
        """
        SELECT
            COUNT(*) AS total_tickets,
            SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress_count,
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) AS resolved_count,
            SUM(CASE WHEN status = 'Open' AND priority = 'Critical' AND assigned_to IS NULL THEN 1 ELSE 0 END) AS critical_unassigned_count,
            SUM(CASE WHEN resolved_at IS NOT NULL AND strftime('%Y-%m', resolved_at) = strftime('%Y-%m', 'now') THEN 1 ELSE 0 END) AS resolved_this_month,
            SUM(CASE WHEN resolved_at IS NOT NULL THEN 1 ELSE 0 END) AS sla_eligible_count,
            SUM(CASE WHEN resolved_at IS NOT NULL AND
                (julianday(resolved_at) - julianday(created_at)) * 1440 <= sla_target_minutes
                THEN 1 ELSE 0 END) AS sla_compliant_count,
            MAX(is_demo) AS contains_demo_records,
            ROUND(AVG(CASE WHEN first_response_at IS NOT NULL
                THEN (julianday(first_response_at) - julianday(created_at)) * 1440
                ELSE NULL END), 1) AS average_first_response_minutes
        FROM tickets
        WHERE deleted_at IS NULL
        """
    ).fetchone()
    median_row = connection.execute(
        """
        WITH response_times AS (
            SELECT (julianday(first_response_at) - julianday(created_at)) * 1440 AS minutes
            FROM tickets
            WHERE deleted_at IS NULL AND first_response_at IS NOT NULL
        ),
        ranked AS (
            SELECT minutes, ROW_NUMBER() OVER (ORDER BY minutes) AS position,
                COUNT(*) OVER () AS sample_size
            FROM response_times
        )
        SELECT ROUND(AVG(minutes), 1) AS median_first_response_minutes
        FROM ranked
        WHERE position IN ((sample_size + 1) / 2, (sample_size + 2) / 2)
        """
    ).fetchone()
    eligible = aggregates["sla_eligible_count"] or 0
    return {
        "total_tickets": aggregates["total_tickets"] or 0,
        "open_count": aggregates["open_count"] or 0,
        "in_progress_count": aggregates["in_progress_count"] or 0,
        "resolved_count": aggregates["resolved_count"] or 0,
        "critical_unassigned_count": aggregates["critical_unassigned_count"] or 0,
        "resolved_this_month": aggregates["resolved_this_month"] or 0,
        "sla_eligible_count": eligible,
        "sla_compliance_rate": round(100 * aggregates["sla_compliant_count"] / eligible, 1) if eligible else None,
        "average_first_response_minutes": aggregates["average_first_response_minutes"],
        "median_first_response_minutes": median_row["median_first_response_minutes"],
        "is_live_telemetry": True,
        "is_illustrative_demo_content": bool(aggregates["contains_demo_records"]),
        "measured_at": utc_now(),
    }


def create_app(database_path: Path = DATABASE_PATH) -> FastAPI:
    started_at = time.monotonic()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        initialize_database(database_path)
        yield

    application = FastAPI(title="Zendesk API", version="1.0.0", lifespan=lifespan)
    application.state.database_path = database_path
    application.state.started_at = started_at

    @application.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        if request.url.path in {"/", "/styles.css", "/app.js", "/favicon.svg"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
                "object-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "font-src 'self'; connect-src 'self'"
            )
        response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        return response

    @application.get("/")
    def home() -> FileResponse:
        return FileResponse(ROOT / "index.html")

    @application.get("/favicon.svg")
    def favicon() -> FileResponse:
        return FileResponse(ROOT / "favicon.svg", media_type="image/svg+xml")

    @application.get("/styles.css")
    def styles() -> FileResponse:
        return FileResponse(ROOT / "styles.css", media_type="text/css")

    @application.get("/app.js")
    def script() -> FileResponse:
        return FileResponse(ROOT / "app.js", media_type="text/javascript")

    @application.get("/api/health")
    def health() -> dict[str, object]:
        try:
            with closing(connect(database_path)) as connection:
                connection.execute("SELECT 1 FROM tickets LIMIT 1").fetchone()
        except sqlite3.Error as error:
            raise HTTPException(status_code=503, detail="Ticket database is unavailable.") from error
        return {
            "status": "healthy",
            "uptime_seconds": int(time.monotonic() - started_at),
            "memory_usage_bytes": process_memory_usage_bytes(),
            "database": "connected",
            "timestamp": utc_now(),
        }

    @application.get("/api/metrics")
    def metrics() -> dict[str, object]:
        with closing(connect(database_path)) as connection:
            return ticket_metrics(connection)

    @application.get("/api/tickets")
    def list_tickets(
        priority: Priority | None = None,
        status: Status | None = None,
        search: str = Query(default="", max_length=160),
    ) -> list[dict[str, object]]:
        clauses = ["deleted_at IS NULL"]
        parameters: list[object] = []
        if priority is not None:
            clauses.append("priority = ?")
            parameters.append(priority)
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status)
        if search.strip():
            term = f"%{search.strip()}%"
            clauses.append("(title LIKE ? OR requester LIKE ? OR legacy_id LIKE ?)")
            parameters.extend([term, term, term])
        with closing(connect(database_path)) as connection:
            rows = connection.execute(
                f"SELECT * FROM tickets WHERE {' AND '.join(clauses)} ORDER BY ticket_number DESC",
                parameters,
            ).fetchall()
        return [row_to_ticket(row) for row in rows]

    @application.get("/api/tickets/{reference}")
    def read_ticket(reference: str) -> dict[str, object]:
        with closing(connect(database_path)) as connection:
            row = get_ticket_row(connection, reference)
            if row is None:
                raise HTTPException(status_code=404, detail="Ticket not found.")
            result = row_to_ticket(row)
            result["auditHistory"] = [
                dict(entry)
                for entry in connection.execute(
                    """
                    SELECT action, performed_by AS performedBy, previous_value AS previousValue,
                        new_value AS newValue, created_at AS createdAt
                    FROM audit_logs WHERE ticket_number = ? ORDER BY id
                    """,
                    (row["ticket_number"],),
                ).fetchall()
            ]
        return result

    @application.post("/api/tickets", status_code=201)
    def create_ticket(ticket: TicketCreate) -> dict[str, object]:
        created_at = utc_now()
        with closing(connect(database_path)) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO tickets
                        (title, requester, category, priority, status, description, created_at, sla_target_minutes)
                    VALUES (?, ?, ?, ?, 'Open', ?, ?, ?)
                    """,
                    (
                        ticket.title,
                        ticket.requester,
                        ticket.category,
                        ticket.priority,
                        ticket.description,
                        created_at,
                        SLA_TARGETS[ticket.priority],
                    ),
                )
                ticket_number = cursor.lastrowid
                add_audit_entry(connection, ticket_number, "TICKET_CREATED", None, ticket_ref(ticket_number))
                row = connection.execute(
                    "SELECT * FROM tickets WHERE ticket_number = ?", (ticket_number,)
                ).fetchone()
                return row_to_ticket(row)

    @application.post("/api/tickets/import-legacy")
    def import_legacy_tickets(payload: LegacyImport) -> dict[str, int]:
        imported_count = 0
        with closing(connect(database_path)) as connection:
            with connection:
                for ticket in payload.tickets:
                    created_at = ticket.createdAt.astimezone(timezone.utc).isoformat(timespec="seconds")
                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO tickets
                            (legacy_id, title, requester, category, priority, status, description,
                             created_at, sla_target_minutes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ticket.id,
                            ticket.title,
                            ticket.requester,
                            ticket.category,
                            ticket.priority,
                            ticket.status,
                            ticket.description,
                            created_at,
                            SLA_TARGETS[ticket.priority],
                        ),
                    )
                    if cursor.rowcount:
                        imported_count += 1
                        add_audit_entry(
                            connection,
                            cursor.lastrowid,
                            "LEGACY_TICKET_IMPORTED",
                            None,
                            ticket_ref(cursor.lastrowid),
                        )
        return {"imported_count": imported_count, "submitted_count": len(payload.tickets)}

    @application.patch("/api/tickets/{reference}")
    def update_ticket(reference: str, update: TicketUpdate) -> dict[str, object]:
        with closing(connect(database_path)) as connection:
            with connection:
                row = get_ticket_row(connection, reference)
                if row is None:
                    raise HTTPException(status_code=404, detail="Ticket not found.")
                changes: dict[str, str] = {}
                if update.status is not None and update.status != row["status"]:
                    changes["status"] = update.status
                if update.priority is not None and update.priority != row["priority"]:
                    changes["priority"] = update.priority
                if not changes:
                    return row_to_ticket(row)

                response_at = row["first_response_at"]
                resolved_at = row["resolved_at"]
                if changes.get("status") == "In Progress" and response_at is None:
                    response_at = utc_now()
                if "status" in changes:
                    resolved_at = utc_now() if changes["status"] == "Resolved" else None
                priority = changes.get("priority", row["priority"])
                connection.execute(
                    """
                    UPDATE tickets
                    SET status = ?, priority = ?, first_response_at = ?, resolved_at = ?,
                        sla_target_minutes = ?
                    WHERE ticket_number = ?
                    """,
                    (
                        changes.get("status", row["status"]),
                        priority,
                        response_at,
                        resolved_at,
                        SLA_TARGETS[priority],
                        row["ticket_number"],
                    ),
                )
                for field, new_value in changes.items():
                    add_audit_entry(
                        connection,
                        row["ticket_number"],
                        f"{field.upper()}_CHANGED",
                        row[field],
                        new_value,
                    )
                updated_row = connection.execute(
                    "SELECT * FROM tickets WHERE ticket_number = ?", (row["ticket_number"],)
                ).fetchone()
                return row_to_ticket(updated_row)

    @application.delete("/api/tickets/{reference}", status_code=204)
    def delete_ticket(reference: str) -> Response:
        with closing(connect(database_path)) as connection:
            with connection:
                row = get_ticket_row(connection, reference)
                if row is None:
                    raise HTTPException(status_code=404, detail="Ticket not found.")
                deleted_at = utc_now()
                connection.execute(
                    "UPDATE tickets SET deleted_at = ? WHERE ticket_number = ?",
                    (deleted_at, row["ticket_number"]),
                )
                add_audit_entry(
                    connection,
                    row["ticket_number"],
                    "TICKET_DELETED",
                    "active",
                    deleted_at,
                )
        return Response(status_code=204)

    return application


app = create_app()
