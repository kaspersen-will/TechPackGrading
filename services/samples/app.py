import logging
import os
import sys

from flask import Flask

import migrate
import web
from samples.routes import bp as samples_bp


def create_app():
    app = Flask(__name__)

    # The schema comes from migrate.py, run before the server starts, not from here.
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is not set")
    app.config["DATABASE_URL"] = os.environ["DATABASE_URL"]
    # Where the specs service is, and how long to wait for it before answering 503.
    app.config["SPECS_URL"] = os.environ.get("SPECS_URL", "http://localhost:8000")
    app.config["SPECS_TIMEOUT_S"] = float(os.environ.get("SPECS_TIMEOUT_S", "5"))

    web.install(app)  # request logs, CORS for UI_ORIGIN, JSON errors, /health
    app.register_blueprint(samples_bp)
    return app


if __name__ == "__main__":
    # Local run without Docker: apply migrations first, as the container entrypoint will.
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    migrate.main()
    app = create_app()
    port = int(os.environ.get("PORT", "8001"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
