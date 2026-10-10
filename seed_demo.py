from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server import DATABASE_PATH, SLA_TARGETS, add_audit_entry, connect, initialize_database, ticket_ref


DEMO_TICKETS = [
    ("VPN connection drops during calls", "Alex Morgan", "Network", "Critical", "Connection drops every few minutes during video calls.", "Open"),
    ("Finance app fails after update", "Sam Rivera", "Software", "High", "The finance client closes after the latest update.", "In Progress"),
    ("Cannot access shared drive", "Jordan Lee", "Account access", "High", "Shared drive prompts for credentials repeatedly.", "Open"),
    ("Laptop battery drains quickly", "Casey Patel", "Hardware", "Medium", "Battery lasts less than one hour away from the dock.", "Resolved"),
    ("Printer queue is stuck", "Taylor Nguyen", "Hardware", "Low", "Jobs remain queued on the second-floor printer.", "Resolved"),
    ("New starter needs account setup", "Avery Chen", "Account access", "Medium", "Prepare accounts and access for a new team member.", "In Progress"),
    ("Video meeting audio is distorted", "Riley Brooks", "Software", "High", "Incoming audio is choppy in team meetings.", "Open"),
    ("Wi-Fi coverage in meeting room", "Morgan Diaz", "Network", "Medium", "Wireless signal drops in the east meeting room.", "Resolved"),
    ("Monitor flickers at startup", "Jamie Kim", "Hardware", "Low", "External display flickers for a minute after login.", "Resolved"),
    ("Repository permission request", "Drew Wilson", "Account access", "Medium", "Read access needed for the mobile application repository.", "In Progress"),
    ("Shared calendar not syncing", "Quinn Foster", "Software", "High", "Recent calendar changes do not appear on mobile.", "Resolved"),
    ("Network drive is read-only", "Skylar Reed", "Network", "Critical", "The operations team cannot save changes to the shared drive.", "In Progress"),
    ("Keyboard replacement request", "Emerson Bell", "Hardware", "Low", "Several keys stick when typing.", "Open"),
    ("Email client asks for password", "Finley Ward", "Software", "Medium", "Password prompt repeats after successful sign-in.", "Resolved"),
    ("MFA device enrollment", "Rowan Scott", "Account access", "Medium", "Enroll a replacement phone for multi-factor authentication.", "In Progress"),
    ("Office network printer offline", "Dakota Young", "Network", "High", "Printer is unreachable from wired desktops.", "Resolved"),
    ("Dock does not detect display", "Reese Adams", "Hardware", "Medium", "External display is not detected after reconnecting the dock.", "In Progress"),
    ("Unexpected account lockout", "Cameron Price", "Account access", "Critical", "Several staff accounts are locked after a sign-in prompt.", "Open"),
    ("Browser extension compatibility", "Parker Ellis", "Software", "Low", "A required browser extension is not loading.", "Resolved"),
    ("Conference room display setup", "Kendall Brooks", "Other", "Medium", "Help connect the presentation display in room Cedar.", "In Progress"),
]


def seed_demo(database_path: Path = DATABASE_PATH) -> int:
    initialize_database(database_path)
    seeded_at = datetime.now(timezone.utc)
    with closing(connect(database_path)) as connection:
        with connection:
            if connection.execute("SELECT 1 FROM tickets WHERE is_demo = 1 LIMIT 1").fetchone():
                return 0
            for index, ticket in enumerate(DEMO_TICKETS):
                title, requester, category, priority, description, status = ticket
                created_at = seeded_at - timedelta(days=index, hours=index % 8)
                first_response_at = (
                    created_at + timedelta(minutes=5 + index * 3)
                    if status != "Open"
                    else None
                )
                resolved_at = (
                    created_at + timedelta(minutes=20 + index * 15)
                    if status == "Resolved"
                    else None
                )
                cursor = connection.execute(
                    """
                    INSERT INTO tickets
                        (title, requester, category, priority, status, description, created_at,
                         first_response_at, resolved_at, sla_target_minutes, assigned_to, is_demo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        f"[DEMO] {title}",
                        requester,
                        category,
                        priority,
                                            status,
                                            description,
                                            created_at.isoformat(timespec="seconds"),
                                            first_response_at.isoformat(timespec="seconds") if first_response_at else None,
                                            resolved_at.isoformat(timespec="seconds") if resolved_at else None,
                                            SLA_TARGETS[priority],
                                            "Support team" if status == "In Progress" else None,
                                        ),
                )
                add_audit_entry(
                    connection,
                    cursor.lastrowid,
                    "DEMO_TICKET_CREATED",
                    None,
                    ticket_ref(cursor.lastrowid),
                )
    return len(DEMO_TICKETS)


if __name__ == "__main__":
    print(f"Seeded {seed_demo()} illustrative demo tickets.")
