import os

from flask import Flask, redirect, url_for

import db
from samples.routes import bp as samples_bp
from samples.store import SCHEMA
from units import mm_to_cm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__)

    data_dir = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
    os.makedirs(data_dir, exist_ok=True)
    app.config["DATABASE"] = os.path.join(data_dir, "samples.db")
    # Where the other service lives. specs_client will call it; templates link to it.
    app.config["SPECS_URL"] = os.environ.get("SPECS_URL", "http://localhost:8000")

    db.init_db(app.config["DATABASE"], [SCHEMA])
    app.register_blueprint(samples_bp)

    @app.template_filter("cm")
    def cm(mm):
        return "—" if mm is None else mm_to_cm(mm)

    @app.context_processor
    def other_service():
        return {"specs_url": app.config["SPECS_URL"]}

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/")
    def index():
        return redirect(url_for("samples.list_rounds"))

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "8001"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
