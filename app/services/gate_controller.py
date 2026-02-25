import json
import sys

import psycopg2.extras
import requests


class GateController:
    """Routes gate-authorization requests to the correct adapter based on
    the operator's ``integration_type``."""

    def __init__(self, db_conn):
        self.conn = db_conn

    def authorize_exit(self, session_id: int) -> dict:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT s.*, o.name AS operator_name,
                       o.integration_type, o.api_base_url, o.api_key
                FROM parking_sessions s
                JOIN parking_operators o ON o.id = s.operator_id
                WHERE s.id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()

        if not row:
            return {"authorized": False, "method": "none", "message": "Session not found"}

        integration = row.get("integration_type") or "mock"

        if integration == "api":
            adapter = ApiGateAdapter(row, self.conn)
            result = adapter.authorize()
            if result is None:
                # Fallback to mock on API failure
                adapter = MockGateAdapter(row, self.conn)
                result = adapter.authorize()
        elif integration == "db_direct":
            adapter = DbGateAdapter(row, self.conn)
            result = adapter.authorize()
        else:
            adapter = MockGateAdapter(row, self.conn)
            result = adapter.authorize()

        # Log the result to notifications_log
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications_log
                        (notification_type, channel, session_id, payload, success)
                    VALUES ('gate_authorization', %s, %s, %s, %s)
                    """,
                    (
                        result["method"],
                        session_id,
                        json.dumps(result),
                        result["authorized"],
                    ),
                )
            self.conn.commit()
        except Exception as e:
            print(f"Failed to log gate authorization: {e}", file=sys.stderr)

        return result


class ApiGateAdapter:
    """Sends an authorize-exit request to the operator's HTTP API."""

    def __init__(self, session_row: dict, db_conn):
        self.session = session_row
        self.conn = db_conn

    def authorize(self) -> dict | None:
        base_url = (self.session.get("api_base_url") or "").rstrip("/")
        api_key = self.session.get("api_key") or ""
        external_id = self.session.get("external_session_id") or str(self.session["id"])

        url = f"{base_url}/sessions/{external_id}/authorize-exit"
        body = {
            "session_id": external_id,
            "plate_number": self.session["plate_number"],
            "action": "authorize_exit",
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(3):  # initial + 2 retries
            try:
                resp = requests.post(url, json=body, headers=headers, timeout=10)
                if resp.status_code == 200:
                    return {
                        "authorized": True,
                        "method": "api",
                        "message": "Gate authorized via API",
                    }
                print(
                    f"Gate API returned {resp.status_code} (attempt {attempt + 1})",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"Gate API error (attempt {attempt + 1}): {e}",
                    file=sys.stderr,
                )

        # All retries exhausted — signal fallback
        return None


class DbGateAdapter:
    """Placeholder for direct-database gate integration."""

    def __init__(self, session_row: dict, db_conn):
        self.session = session_row
        self.conn = db_conn

    def authorize(self) -> dict:
        op_id = self.session.get("operator_id")
        print(
            f"db_direct not yet implemented for operator {op_id}",
            file=sys.stderr,
        )
        return {
            "authorized": False,
            "method": "db_direct",
            "message": "Not implemented",
        }


class MockGateAdapter:
    """Logs a mock authorization — used in development and as API fallback."""

    def __init__(self, session_row: dict, db_conn):
        self.session = session_row
        self.conn = db_conn

    def authorize(self) -> dict:
        plate = self.session["plate_number"]
        operator_name = self.session.get("operator_name", "unknown")
        print(f"MOCK GATE: Authorizing exit for plate {plate} at {operator_name}")
        return {
            "authorized": True,
            "method": "mock",
            "message": "Mock gate opened",
        }
