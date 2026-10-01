import os
from flask import Flask, redirect, url_for
import db
from samples.routes import bp as samples_bp
from samples.store import SCHEMA as SAMPLES_SCHEMA
from specs.routes import bp as specs_bp
from specs.store import SCHEMA as SPECS_SCHEMA
from units import mm_to_cm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_app():
    app = Flask(__name__)

    data_dir = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
    os.makedirs(data_dir, exist_ok=True)
    app.config["DATABASE"] = os.path.join(data_dir, "techpack.db")

    db.init_db(app.config["DATABASE"], [SPECS_SCHEMA, SAMPLES_SCHEMA])
    app.register_blueprint(specs_bp)
    app.register_blueprint(samples_bp)

    # Shared by both domains' templates, like units.py is shared by their code.
    @app.template_filter("cm")
    def cm(mm):
        return "—" if mm is None else mm_to_cm(mm)

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
