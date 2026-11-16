import os

from flask import Flask, redirect, url_for

import db
from specs.routes import bp as specs_bp
from specs.store import SCHEMA
from units import mm_to_cm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__)

    data_dir = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
    os.makedirs(data_dir, exist_ok=True)
    app.config["DATABASE"] = os.path.join(data_dir, "specs.db")
    # Where the other service lives. Only used for links until the static UI replaces the templates.
    app.config["SAMPLES_URL"] = os.environ.get("SAMPLES_URL", "http://localhost:8001")

    db.init_db(app.config["DATABASE"], [SCHEMA])
    app.register_blueprint(specs_bp)

    @app.template_filter("cm")
    def cm(mm):
        return "—" if mm is None else mm_to_cm(mm)

    @app.context_processor
    def other_service():
        return {"samples_url": app.config["SAMPLES_URL"]}

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/")
    def index():
        return redirect(url_for("specs.list_styles"))

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
