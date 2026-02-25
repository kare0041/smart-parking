import json
import sys

import psycopg2
import psycopg2.extras

from config import Config


def expire_overstayed_sessions(app):
    """Background job: mark paid sessions whose grace period has elapsed as expired."""
    try:
        with app.app_context():
            conn = psycopg2.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                dbname=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
            )
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT id, plate_number, operator_id
                        FROM parking_sessions
                        WHERE status = 'paid'
                          AND grace_period_end < NOW()
                        """
                    )
                    expired = cur.fetchall()

                    for session in expired:
                        cur.execute(
                            "UPDATE parking_sessions SET status = 'expired' WHERE id = %s",
                            (session["id"],),
                        )
                        cur.execute(
                            """
                            INSERT INTO notifications_log
                                (notification_type, channel, session_id, payload)
                            VALUES ('grace_period_expired', 'system', %s, %s)
                            """,
                            (
                                session["id"],
                                json.dumps({
                                    "plate": session["plate_number"],
                                    "operator_id": session["operator_id"],
                                }),
                            ),
                        )
                        print(
                            f"Session {session['id']} for plate {session['plate_number']} "
                            f"grace period expired"
                        )

                conn.commit()
            finally:
                conn.close()

    except Exception as e:
        print(f"Grace period scheduler error: {e}", file=sys.stderr)
