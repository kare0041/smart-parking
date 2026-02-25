import json
import sys

import psycopg2.extras
from flask import Blueprint, jsonify, request

from app import get_db
from app.services.gate_controller import GateController

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")


@webhooks_bp.route("/mtn-momo/callback", methods=["POST"])
def mtn_momo_callback():
    """Receive payment status updates pushed by MTN MoMo."""
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"received": True}), 200

        transaction_reference = data.get("externalId")
        callback_status = data.get("status")
        financial_txn_id = data.get("financialTransactionId")

        db = get_db()
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Look up the payment
            cur.execute(
                "SELECT * FROM payments WHERE transaction_reference = %s",
                (transaction_reference,),
            )
            payment = cur.fetchone()

        if not payment:
            return jsonify({"error": "Payment not found"}), 404

        # Idempotency: already terminal → no-op
        if payment["status"] in ("completed", "failed"):
            return jsonify({"received": True}), 200

        if callback_status == "SUCCESSFUL":
            with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Update payment
                cur.execute(
                    """
                    UPDATE payments
                    SET status = 'completed',
                        confirmed_at = NOW(),
                        momo_transaction_id = %s
                    WHERE transaction_reference = %s
                    """,
                    (financial_txn_id, transaction_reference),
                )

                # Fetch session + operator to get grace_period_minutes
                cur.execute(
                    """
                    SELECT s.id AS session_id, o.grace_period_minutes
                    FROM parking_sessions s
                    JOIN parking_operators o ON o.id = s.operator_id
                    WHERE s.id = %s
                    """,
                    (payment["session_id"],),
                )
                session_op = cur.fetchone()

                if session_op:
                    grace_minutes = session_op["grace_period_minutes"] or 15
                    cur.execute(
                        """
                        UPDATE parking_sessions
                        SET status = 'paid',
                            grace_period_end = NOW() + make_interval(mins => %s)
                        WHERE id = %s
                        """,
                        (grace_minutes, session_op["session_id"]),
                    )

                # Log to notifications_log
                cur.execute(
                    """
                    INSERT INTO notifications_log
                        (notification_type, channel, session_id, payload)
                    VALUES ('payment_confirmed', 'webhook', %s, %s)
                    """,
                    (payment["session_id"], json.dumps(data)),
                )

            db.commit()

            # Authorize gate exit
            try:
                GateController(db).authorize_exit(payment["session_id"])
            except Exception as e:
                print(f"Gate authorization error: {e}", file=sys.stderr)

            return jsonify({"received": True}), 200

        if callback_status == "FAILED":
            with db.cursor() as cur:
                cur.execute(
                    "UPDATE payments SET status = 'failed' WHERE transaction_reference = %s",
                    (transaction_reference,),
                )
            db.commit()
            return jsonify({"received": True}), 200

        # Unknown status — acknowledge anyway
        return jsonify({"received": True}), 200

    except Exception as e:
        print(f"Webhook error: {e}", file=sys.stderr)
        return jsonify({"received": True}), 200


@webhooks_bp.route("/operator/session-update", methods=["POST"])
def operator_session_update():
    """Receive session lifecycle events from parking operators."""
    data = request.get_json(silent=True) or {}

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications_log
                    (notification_type, channel, payload)
                VALUES ('operator_session_update', 'webhook', %s)
                """,
                (json.dumps(data),),
            )
        db.commit()
    except Exception as e:
        print(f"Failed to log operator session update: {e}", file=sys.stderr)

    # TODO: Implement full sync logic — create/update parking_sessions based on event type

    return jsonify({"received": True, "status": "logged"}), 200
