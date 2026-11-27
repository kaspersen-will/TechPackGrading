"""What every service does around its own routes. Copied, not shared, between the two services.

- one log line per request on stdout: method, path, status, duration;
- CORS: only the UI's origin (UI_ORIGIN) may call this service from a browser;
- errors come back as JSON {"error": "..."}, never as an HTML page or a stack trace;
- GET /health: 200 if this service can write to its own database, 503 if not.
"""

import logging
import os
import sys
import time

from flask import g, jsonify, request
from werkzeug.exceptions import HTTPException

import db

log = logging.getLogger("request")


def install(app):
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app.config["UI_ORIGIN"] = os.environ.get("UI_ORIGIN", "http://localhost:8080")
    app.config["GIT_SHA"] = os.environ.get("GIT_SHA", "dev")
    app.config["HEALTH_DB_TIMEOUT_S"] = float(os.environ.get("HEALTH_DB_TIMEOUT_S", "5"))

    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.after_request
    def cors_and_log(response):
        origin = request.headers.get("Origin")
        if origin and origin == app.config["UI_ORIGIN"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Max-Age"] = "600"
        response.vary.add("Origin")  # a cache must not hand one origin's answer to another
        duration_ms = (time.perf_counter() - g.get("started", time.perf_counter())) * 1000
        log.info("%s %s %d %.1fms", request.method, request.path, response.status_code, duration_ms)
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        log.exception("unhandled error on %s %s", request.method, request.path)
        return jsonify(error="internal error"), 500

    @app.get("/health")
    def health():
        # A real write to this service's own database, with a short retry budget so
        # the check answers within seconds even when the database is down or paused.
        body = {"version": app.config["GIT_SHA"]}
        try:
            conn = db.connect(app.config["DATABASE_URL"], timeout_s=app.config["HEALTH_DB_TIMEOUT_S"])
            try:
                with conn:
                    updated = conn.execute(
                        "UPDATE health_check SET checked_at = SYSUTCDATETIME() WHERE id = 1"
                    ).rowcount
            finally:
                conn.close()
            if updated != 1:
                raise RuntimeError("health_check row is missing")
        except Exception as error:  # noqa: BLE001 -- any failure means "not healthy", never a 500
            logging.getLogger("health").warning("database check failed: %s", str(error)[:200])
            return jsonify(status="unavailable", db="error", **body), 503
        return jsonify(status="ok", db="ok", **body)
