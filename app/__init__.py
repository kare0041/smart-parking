import atexit
import os

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
    from app.routes.webhooks import webhooks_bp

    app.register_blueprint(mock_bp)
    app.register_blueprint(parking_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(webhooks_bp)

    init_scheduler(app)

    return app


def init_scheduler(app):
    """Start the APScheduler background job for grace-period expiry.

    Guarded so it only starts once (avoids double-start with Flask reloader).
    """
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    from apscheduler.schedulers.background import BackgroundScheduler
    from app.tasks.grace_period import expire_overstayed_sessions

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        expire_overstayed_sessions,
        trigger="interval",
        seconds=60,
        args=[app],
        id="expire_overstayed_sessions",
    )
    scheduler.start()
    atexit.register(scheduler.shutdown)
