import psycopg2
from flask import Flask, g, jsonify

from config import Config


def get_db():
    """Get a database connection for the current request."""
    if "db" not in g:
        g.db = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
        )
    return g.db


def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.teardown_appcontext(close_db)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    from app.routes.mock import mock_bp
    from app.routes.parking import parking_bp
    from app.routes.payment import payment_bp

    app.register_blueprint(mock_bp)
    app.register_blueprint(parking_bp)
    app.register_blueprint(payment_bp)

    return app
