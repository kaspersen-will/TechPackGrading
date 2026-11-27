import logging
import os
import sys

from flask import Flask

import migrate
import web
from specs.routes import bp as specs_bp


def create_app():
    app = Flask(__name__)

    # The schema comes from migrate.py, run before the server starts, not from here.
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is not set")
    app.config["DATABASE_URL"] = os.environ["DATABASE_URL"]

    web.install(app)  # request logs, CORS for UI_ORIGIN, JSON errors, /health
    app.register_blueprint(specs_bp)
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
