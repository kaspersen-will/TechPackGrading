import logging
import os
import sys

from flask import Flask, redirect, url_for

import migrate
from specs.routes import bp as specs_bp
from units import mm_to_cm


def create_app():
    app = Flask(__name__)

    # The schema comes from migrate.py, run before the server starts, not from here.
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is not set")
    app.config["DATABASE_URL"] = os.environ["DATABASE_URL"]
    # Where the other service lives. Only used for links until the static UI replaces the templates.
    app.config["SAMPLES_URL"] = os.environ.get("SAMPLES_URL", "http://localhost:8001")

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
    # Local run without Docker: apply migrations first, as the container entrypoint will.
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    migrate.main()
    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
