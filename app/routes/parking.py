import math
from datetime import datetime, timezone

from flask import (
    Blueprint,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from app import get_db
from app.services.parking_sync import MockOperatorClient

parking_bp = Blueprint("parking", __name__)


def _client() -> MockOperatorClient:
    return MockOperatorClient(get_db())


@parking_bp.route("/")
def lookup_form():
    saved_plate = request.cookies.get("saved_plate", "")
    return render_template("lookup.html", saved_plate=saved_plate)


@parking_bp.route("/lookup", methods=["POST"])
def lookup():
    plate = request.form.get("plate_number", "").strip().upper()
    if not plate:
        return render_template("lookup.html", saved_plate="", error="Please enter a plate number.")

    sessions = _client().get_active_sessions_for_plate(plate)

    if len(sessions) == 0:
        resp = make_response(
            render_template("lookup.html", saved_plate=plate, error=f"No active sessions found for {plate}.")
        )
        resp.set_cookie("saved_plate", plate, max_age=7 * 24 * 3600)
        return resp

    if len(sessions) == 1:
        resp = make_response(redirect(url_for("parking.session_detail", session_id=sessions[0]["id"])))
        resp.set_cookie("saved_plate", plate, max_age=7 * 24 * 3600)
        return resp

    # Multiple sessions
    resp = make_response(
        render_template("sessions_list.html", plate=plate, sessions=sessions)
    )
    resp.set_cookie("saved_plate", plate, max_age=7 * 24 * 3600)
    return resp


@parking_bp.route("/session/<int:session_id>")
def session_detail(session_id):
    session = _client().get_session_by_id(session_id)
    if not session or session["status"] not in ("active", "paid"):
        flash("Session not found or no longer active.", "error")
        return redirect(url_for("parking.lookup_form"))
    return render_template("session.html", session=session)


@parking_bp.route("/api/v1/session/<int:session_id>")
def session_api(session_id):
    session = _client().get_session_by_id(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    entry_time = datetime.fromisoformat(session["entry_time"])
    now = datetime.now(timezone.utc)
    elapsed = now - entry_time
    elapsed_seconds = int(elapsed.total_seconds())
    elapsed_hours = elapsed.total_seconds() / 3600
    billable_hours = max(math.ceil(elapsed_hours), 1)
    next_fee_increase_in_seconds = int((billable_hours * 3600) - elapsed.total_seconds())
    if next_fee_increase_in_seconds < 0:
        next_fee_increase_in_seconds = 0

    session["elapsed_seconds"] = elapsed_seconds
    session["next_fee_increase_in_seconds"] = next_fee_increase_in_seconds
    return jsonify(session)
