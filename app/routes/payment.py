import math
import re
import sys
from datetime import datetime, timezone

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from app import get_db
from app.services.mtn_momo import MtnMomoClient
from app.services.parking_sync import MockOperatorClient

payment_bp = Blueprint("payment", __name__, url_prefix="/pay")

PHONE_REGEX = re.compile(r"^07[89]\d{7}$")


def _momo():
    return MtnMomoClient(get_db())


def _parking():
    return MockOperatorClient(get_db())


def _compute_fee(session: dict) -> int:
    entry_time = datetime.fromisoformat(session["entry_time"])
    now = datetime.now(timezone.utc)
    elapsed_hours = (now - entry_time).total_seconds() / 3600
    billable_hours = max(math.ceil(elapsed_hours), 1)
    return billable_hours * session["hourly_rate_rwf"]


@payment_bp.route("/<int:session_id>")
def payment_form(session_id):
    session = _parking().get_session_by_id(session_id)
    if not session or session["status"] != "active":
        flash("Session not found or no longer active.", "error")
        return redirect(url_for("parking.lookup_form"))

    fee = _compute_fee(session)
    return render_template("payment.html", session=session, fee=fee)


@payment_bp.route("/<int:session_id>/initiate", methods=["POST"])
def initiate_payment(session_id):
    phone_number = request.form.get("phone_number", "").strip()
    payment_method = request.form.get("payment_method", "")

    if not PHONE_REGEX.match(phone_number):
        flash("Please enter a valid MTN phone number (e.g. 0781234567).", "error")
        return redirect(url_for("payment.payment_form", session_id=session_id))

    if payment_method != "mtn_momo":
        flash("Only MTN Mobile Money is currently supported.", "error")
        return redirect(url_for("payment.payment_form", session_id=session_id))

    session = _parking().get_session_by_id(session_id)
    if not session or session["status"] != "active":
        flash("Session not found or no longer active.", "error")
        return redirect(url_for("parking.lookup_form"))

    momo = _momo()

    # Check for existing pending payment
    pending = momo.get_pending_payment(session_id)
    if pending:
        return redirect(
            url_for(
                "payment.payment_status",
                session_id=session_id,
                transaction_reference=pending["transaction_reference"],
            )
        )

    fee = _compute_fee(session)

    try:
        reference = momo.request_to_pay(
            session_id=session_id,
            amount_rwf=fee,
            phone_number=phone_number,
            location_name=session.get("operator_location", ""),
        )
    except Exception as e:
        print(f"Payment initiation error: {e}", file=sys.stderr)
        flash("Could not initiate payment. Please try again.", "error")
        return redirect(url_for("payment.payment_form", session_id=session_id))

    return redirect(
        url_for(
            "payment.payment_status",
            session_id=session_id,
            transaction_reference=reference,
        )
    )


@payment_bp.route("/<int:session_id>/status/<transaction_reference>")
def payment_status(session_id, transaction_reference):
    session = _parking().get_session_by_id(session_id)

    # Get phone number from payments table
    import psycopg2.extras

    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT phone_number FROM payments WHERE transaction_reference = %s",
            (transaction_reference,),
        )
        payment_row = cur.fetchone()

    phone_number = payment_row["phone_number"] if payment_row else ""

    return render_template(
        "payment_status.html",
        session=session,
        session_id=session_id,
        transaction_reference=transaction_reference,
        phone_number=phone_number,
    )


@payment_bp.route("/api/status/<transaction_reference>")
def payment_status_api(transaction_reference):
    try:
        result = _momo().confirm_payment(transaction_reference)
        return jsonify(result)
    except Exception as e:
        print(f"Payment status check error: {e}", file=sys.stderr)
        return jsonify({"success": False, "reason": str(e)}), 500
