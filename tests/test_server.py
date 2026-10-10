import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from server import connect, create_app
from seed_demo import seed_demo


class TicketApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "tickets.sqlite3"
        self.client_context = TestClient(create_app(self.database_path))
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def create_ticket(self, **overrides: object) -> dict[str, object]:
        ticket = {
            "title": "Unable to join office Wi-Fi",
            "requester": "Morgan Lee",
            "category": "Network",
            "priority": "High",
            "description": "Laptop cannot authenticate to the office network.",
        }
        ticket.update(overrides)
        response = self.client.post("/api/tickets", json=ticket)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_health_checks_database(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "connected")
        self.assertGreaterEqual(response.json()["uptime_seconds"], 0)
        memory_usage = response.json()["memory_usage_bytes"]
        if memory_usage is not None:
            self.assertGreater(memory_usage, 0)

    def test_brand_assets_and_security_headers(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("<title>Zendesk — IT Support</title>", page.text)
        self.assertIn('href="/favicon.svg"', page.text)
        self.assertEqual(page.headers["x-content-type-options"], "nosniff")
        self.assertEqual(page.headers["x-frame-options"], "DENY")
        self.assertIn("default-src 'self'", page.headers["content-security-policy"])

        favicon = self.client.get("/favicon.svg")
        self.assertEqual(favicon.status_code, 200)
        self.assertEqual(favicon.headers["content-type"], "image/svg+xml")
        self.assertIn("<svg", favicon.text)
        self.assertEqual(self.client.get("/api/health").headers["cache-control"], "no-store")

        api_docs = self.client.get("/docs")
        self.assertEqual(api_docs.status_code, 200)
        self.assertIn("swagger-ui", api_docs.text)

    def test_create_filter_lookup_and_update_audit(self) -> None:
        high_ticket = self.create_ticket()
        self.create_ticket(title="Keyboard failure", priority="Low", requester="Taylor Reed")
        reference = high_ticket["id"]

        filtered = self.client.get("/api/tickets", params={"priority": "High"})
        self.assertEqual([ticket["id"] for ticket in filtered.json()], [reference])
        self.assertEqual(self.client.get(f"/api/tickets/{reference}").status_code, 200)

        updated = self.client.patch(
            f"/api/tickets/{reference}",
            json={"status": "In Progress", "priority": "Critical"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["priority"], "Critical")
        self.assertEqual(updated.json()["slaTargetMinutes"], 60)
        detail = self.client.get(f"/api/tickets/{reference}").json()
        self.assertIsNotNone(detail["firstResponseAt"])
        self.assertEqual(
            [entry["action"] for entry in detail["auditHistory"]],
            ["TICKET_CREATED", "STATUS_CHANGED", "PRIORITY_CHANGED"],
        )

    def test_rejects_whitespace_and_invalid_status(self) -> None:
        invalid_ticket = {
            "title": "  ",
            "requester": "Morgan Lee",
            "category": "Network",
            "priority": "High",
            "description": "Network unavailable",
        }
        self.assertEqual(self.client.post("/api/tickets", json=invalid_ticket).status_code, 422)
        ticket = self.create_ticket()
        self.assertEqual(
            self.client.patch(f"/api/tickets/{ticket['id']}", json={"status": "Closed"}).status_code,
            422,
        )

    def test_lookup_and_soft_delete_preserve_audit(self) -> None:
        ticket = self.create_ticket()
        deleted = self.client.delete(f"/api/tickets/{ticket['id']}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get(f"/api/tickets/{ticket['id']}").status_code, 404)
        with closing(connect(self.database_path)) as connection:
            actions = connection.execute(
                "SELECT action FROM audit_logs ORDER BY id"
            ).fetchall()
        self.assertEqual([row["action"] for row in actions], ["TICKET_CREATED", "TICKET_DELETED"])

    def test_legacy_import_is_lossless_and_idempotent(self) -> None:
        legacy = {
            "tickets": [{
                "id": "1728488400000-ab12cd",
                "title": "Legacy laptop issue",
                "requester": "Casey Park",
                "category": "Hardware",
                "priority": "Medium",
                "status": "Open",
                "description": "Imported from browser storage.",
                "createdAt": "2026-10-02T12:00:00.000Z",
            }]
        }
        first = self.client.post("/api/tickets/import-legacy", json=legacy).json()
        second = self.client.post("/api/tickets/import-legacy", json=legacy).json()
        self.assertEqual(first["imported_count"], 1)
        self.assertEqual(second["imported_count"], 0)
        result = self.client.get("/api/tickets", params={"search": "Legacy laptop"})
        self.assertEqual(len(result.json()), 1)
        self.assertEqual(
            self.client.get("/api/tickets/REQ-AB12CD").status_code,
            200,
        )

    def test_metrics_use_recorded_timestamps_and_explain_seed_data(self) -> None:
        fast = self.create_ticket(title="Fast response")
        slow = self.create_ticket(title="Slow response", priority="Low")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        fast_created = now - timedelta(minutes=30)
        slow_created = now - timedelta(minutes=5000)
        with closing(connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """
                    UPDATE tickets SET created_at = ?, first_response_at = ?, resolved_at = ?
                    WHERE ticket_number = ?
                    """,
                    (
                        fast_created.isoformat(),
                        (fast_created + timedelta(minutes=4)).isoformat(),
                        (now - timedelta(minutes=1)).isoformat(),
                        int(fast["id"].split("-")[1]),
                    ),
                )
                connection.execute(
                    """
                    UPDATE tickets SET created_at = ?, first_response_at = ?, resolved_at = ?, is_demo = 1
                    WHERE ticket_number = ?
                    """,
                    (
                        slow_created.isoformat(),
                        (slow_created + timedelta(minutes=10)).isoformat(),
                        (now - timedelta(minutes=1)).isoformat(),
                        int(slow["id"].split("-")[1]),
                    ),
                )
        metrics = self.client.get("/api/metrics").json()
        self.assertEqual(metrics["total_tickets"], 2)
        self.assertEqual(metrics["median_first_response_minutes"], 7)
        self.assertEqual(metrics["sla_compliance_rate"], 50)
        self.assertTrue(metrics["is_live_telemetry"])
        self.assertTrue(metrics["is_illustrative_demo_content"])
        self.assertEqual(metrics["resolved_this_month"], 2)

    def test_empty_time_metrics_are_unavailable_and_demo_seed_is_idempotent(self) -> None:
        empty_metrics = self.client.get("/api/metrics").json()
        self.assertIsNone(empty_metrics["median_first_response_minutes"])
        self.assertIsNone(empty_metrics["sla_compliance_rate"])
        self.assertFalse(empty_metrics["is_illustrative_demo_content"])

        self.assertEqual(seed_demo(self.database_path), 20)
        self.assertEqual(seed_demo(self.database_path), 0)
        metrics = self.client.get("/api/metrics").json()
        self.assertEqual(metrics["total_tickets"], 20)
        self.assertTrue(metrics["is_illustrative_demo_content"])
        demo_tickets = self.client.get("/api/tickets", params={"priority": "Critical"}).json()
        self.assertTrue(all(ticket["isDemo"] for ticket in demo_tickets))


if __name__ == "__main__":
    unittest.main()
