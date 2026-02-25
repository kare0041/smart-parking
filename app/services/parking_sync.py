import psycopg2.extras
from app.models.session import ParkingSession


class MockOperatorClient:
    """Simulates a parking operator's system for development and testing."""

    def __init__(self, db_conn):
        self.conn = db_conn

    def seed_operators(self) -> list[dict]:
        """Insert 2 mock parking operators if they do not already exist."""
        operators = [
            {
                "name": "Kigali Heights Parking",
                "location_name": "Kigali Heights Mall",
                "address": "KG 7 Ave, Kigali",
                "latitude": -1.9441,
                "longitude": 30.0619,
                "hourly_rate": 500,
                "grace_period_minutes": 15,
            },
            {
                "name": "UTC Parking",
                "location_name": "Union Trade Centre",
                "address": "KN 4 Ave, Kigali",
                "latitude": -1.9500,
                "longitude": 30.0588,
                "hourly_rate": 1000,
                "grace_period_minutes": 10,
            },
        ]

        results = []
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for op in operators:
                cur.execute(
                    "SELECT id, name FROM parking_operators WHERE name = %(name)s",
                    {"name": op["name"]},
                )
                existing = cur.fetchone()
                if existing:
                    results.append(
                        {"id": existing["id"], "name": existing["name"], "status": "already_exists"}
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO parking_operators
                            (name, location_name, address, latitude, longitude,
                             hourly_rate, grace_period_minutes)
                        VALUES
                            (%(name)s, %(location_name)s, %(address)s, %(latitude)s,
                             %(longitude)s, %(hourly_rate)s, %(grace_period_minutes)s)
                        RETURNING id, name
                        """,
                        op,
                    )
                    row = cur.fetchone()
                    results.append(
                        {"id": row["id"], "name": row["name"], "status": "created"}
                    )
            self.conn.commit()
        return results

    def simulate_car_entry(self, plate_number: str, operator_id: int) -> dict:
        """Create a new active parking session for a car entering the lot."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get the operator's hourly rate
            cur.execute(
                "SELECT hourly_rate FROM parking_operators WHERE id = %s",
                (operator_id,),
            )
            operator = cur.fetchone()
            if not operator:
                raise ValueError(f"Operator with id {operator_id} not found")

            cur.execute(
                """
                INSERT INTO parking_sessions
                    (plate_number, operator_id, entry_time, hourly_rate_rwf, status)
                VALUES
                    (%s, %s, NOW(), %s, 'active')
                RETURNING *
                """,
                (plate_number.upper(), operator_id, operator["hourly_rate"]),
            )
            row = cur.fetchone()
            self.conn.commit()

        session = _row_to_session(row)
        return session.to_dict()

    def simulate_car_exit(self, session_id: int) -> dict:
        """Mark a parking session as exited with the current timestamp."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE parking_sessions
                SET exit_time = NOW(), status = 'exited'
                WHERE id = %s
                RETURNING *
                """,
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Session with id {session_id} not found")
            self.conn.commit()

        session = _row_to_session(row)
        return session.to_dict()

    def get_active_sessions_for_plate(self, plate_number: str) -> list[dict]:
        """Return all active sessions for a plate number, joined with operator info."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    s.*,
                    o.name AS operator_name,
                    o.location_name AS operator_location,
                    o.address AS operator_address
                FROM parking_sessions s
                JOIN parking_operators o ON o.id = s.operator_id
                WHERE UPPER(s.plate_number) = UPPER(%s)
                  AND s.status = 'active'
                ORDER BY s.entry_time DESC
                """,
                (plate_number,),
            )
            rows = cur.fetchall()

        return [_row_to_session(r).to_dict() for r in rows]

    def get_session_by_id(self, session_id: int) -> dict | None:
        """Return a single session joined with operator details."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    s.*,
                    o.name AS operator_name,
                    o.location_name AS operator_location,
                    o.address AS operator_address
                FROM parking_sessions s
                JOIN parking_operators o ON o.id = s.operator_id
                WHERE s.id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()

        if not row:
            return None
        return _row_to_session(row).to_dict()


def _row_to_session(row: dict) -> ParkingSession:
    """Convert a database row dict into a ParkingSession dataclass."""
    return ParkingSession(
        id=row["id"],
        external_session_id=row.get("external_session_id"),
        operator_id=row.get("operator_id"),
        plate_number=row["plate_number"],
        entry_time=row["entry_time"],
        exit_time=row.get("exit_time"),
        status=row.get("status", "active"),
        hourly_rate_rwf=row["hourly_rate_rwf"],
        grace_period_end=row.get("grace_period_end"),
        last_synced_at=row.get("last_synced_at"),
        created_at=row.get("created_at"),
        operator_name=row.get("operator_name"),
        operator_location=row.get("operator_location"),
        operator_address=row.get("operator_address"),
    )
