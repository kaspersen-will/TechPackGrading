"""JSON API for Specs & Grading. Every length is integer mm; the UI converts to cm.

No grading math lives here. Status codes: 400 for a body that can't be used,
404 for an unknown id, 409 for a duplicate code, 422 for a spec that can't be
graded yet (a grade rule is missing).
"""

from contextlib import closing

from flask import Blueprint, abort, current_app, jsonify, request

import db
from specs import store
from specs.grading import GradingError

bp = Blueprint("specs", __name__, url_prefix="/styles")


def _connect():
    # closing() because `with conn:` only commits/rolls back; it never closes.
    return closing(db.connect(current_app.config["DATABASE_URL"]))


def _body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "the body must be a JSON object")
    return body


def _text(body, field):
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        abort(400, f"{field} is required")
    return value.strip()


def _style_or_404(conn, style_id):
    data = store.get_style(conn, style_id)
    if data is None:
        abort(404, f"no style {style_id}")
    return data


@bp.get("")
def list_styles():
    with _connect() as conn:
        return jsonify(store.list_styles(conn))


@bp.post("")
def create_style():
    body = _body()
    sizes = body.get("sizes")
    if not isinstance(sizes, list) or not all(isinstance(s, str) for s in sizes):
        abort(400, "sizes must be a list of size labels, smallest first")
    with _connect() as conn:
        try:
            style_id = store.create_style(
                conn, _text(body, "code"), _text(body, "name"),
                [s.strip() for s in sizes], _text(body, "base_size"),
            )
        except GradingError as error:
            abort(400, str(error))
        except db.IntegrityError:
            abort(409, "that style code is already used")
    return jsonify(id=style_id), 201, {"Location": f"/styles/{style_id}"}


@bp.get("/<int:style_id>")
def show_style(style_id):
    with _connect() as conn:
        data = _style_or_404(conn, style_id)
    # One list of POMs, each carrying its own rules and size run, instead of
    # dicts keyed by pom id (JSON object keys can only be strings).
    poms = [
        {**pom, "rules": data["rules"][pom["id"]], "size_run": data["size_run"][pom["id"]]}
        for pom in data["poms"]
    ]
    return jsonify(style=data["style"], sizes=[s["label"] for s in data["sizes"]], poms=poms)


@bp.delete("/<int:style_id>")
def delete_style(style_id):
    with _connect() as conn:
        if not store.delete_style(conn, style_id):
            abort(404, f"no style {style_id}")
    return "", 204


@bp.post("/<int:style_id>/poms")
def add_pom(style_id):
    body = _body()
    with _connect() as conn:
        _style_or_404(conn, style_id)
        try:
            pom_id = store.add_point_of_measure(
                conn, style_id, _text(body, "code"), _text(body, "description"),
                body.get("base_value_mm"), body.get("tolerance_mm"),
            )
        except GradingError as error:
            abort(400, str(error))
        except db.IntegrityError:
            abort(409, "that point of measure code is already used on this style")
    return jsonify(id=pom_id), 201


@bp.put("/<int:style_id>/poms/<int:pom_id>/rules")
def set_rules(style_id, pom_id):
    increments = _body().get("increments_mm")
    if not isinstance(increments, dict):
        abort(400, "increments_mm must map size labels to whole mm")
    with _connect() as conn:
        data = _style_or_404(conn, style_id)
        if pom_id not in data["rules"]:
            abort(404, f"style {style_id} has no point of measure {pom_id}")
        # Check every value before writing any, so one bad value saves nothing.
        gradable = {s["label"] for s in data["sizes"][1:]}
        for label, increment_mm in increments.items():
            if label not in gradable:
                abort(400, f"{label!r} is not a size of this style that takes a grade rule")
            if isinstance(increment_mm, bool) or not isinstance(increment_mm, int):
                abort(400, f"{label}: {increment_mm!r} is not a whole number of mm")
        for label, increment_mm in increments.items():
            store.set_grade_rule(conn, pom_id, label, increment_mm)
    return "", 204


@bp.get("/<int:style_id>/spec/<size_label>")
def graded_spec(style_id, size_label):
    """The seam. The samples service calls this before it records a round."""
    with _connect() as conn:
        try:
            return jsonify(store.get_graded_spec(conn, style_id, size_label))
        except store.UnknownStyleOrSize as error:
            abort(404, str(error))
        except GradingError as error:
            abort(422, str(error))
