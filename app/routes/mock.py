from flask import Blueprint, jsonify, request

from app import get_db
from app.services.parking_sync import MockOperatorClient

mock_bp = Blueprint("mock", __name__, url_prefix="/mock")


def _client() -> MockOperatorClient:
    return MockOperatorClient(get_db())


@mock_bp.route("/seed", methods=["GET"])
def seed():
    results = _client().seed_operators()
    return jsonify({"message": "Seed complete", "operators": results})


@mock_bp.route("/entry", methods=["POST"])
def entry():
    data = request.get_json()
    if not data or "plate_number" not in data or "operator_id" not in data:
        return jsonify({"error": "plate_number and operator_id are required"}), 400

    try:
        session = _client().simulate_car_entry(
            plate_number=data["plate_number"],
            operator_id=int(data["operator_id"]),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify(session), 201


@mock_bp.route("/exit", methods=["POST"])
def exit_session():
    data = request.get_json()
    if not data or "session_id" not in data:
        return jsonify({"error": "session_id is required"}), 400

    try:
        session = _client().simulate_car_exit(session_id=int(data["session_id"]))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify(session)


@mock_bp.route("/sessions/<plate>", methods=["GET"])
def active_sessions(plate):
    sessions = _client().get_active_sessions_for_plate(plate)
    return jsonify({"plate_number": plate.upper(), "active_sessions": sessions})
