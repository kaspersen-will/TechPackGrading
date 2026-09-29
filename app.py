import os
from flask import Flask
import db
from specs.store import SCHEMA

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_app():
    app = Flask(__name__)

    data_dir = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
    os.makedirs(data_dir, exist_ok=True)
    app.config["DATABASE"] = os.path.join(data_dir, "techpack.db")

    db.init_db(app.config["DATABASE"], [SCHEMA])

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
