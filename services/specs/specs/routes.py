"""HTTP layer for Specs & Grading. Parses cm form input to mm, calls the store, renders.


No grading math lives here. Errors re-render the page with a 400 instead of
using flash(), so the app needs no sessions and no SECRET_KEY.
"""

import sqlite3
from contextlib import closing

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

import db
from specs import store
from specs.grading import GradingError
from units import cm_to_mm

bp = Blueprint("specs", __name__, template_folder="templates", url_prefix="/styles")


def _connect():
    # closing() because `with conn:` only commits/rolls back; it never closes.
    return closing(db.get_connection(current_app.config["DATABASE"]))


def _style_or_404(conn, style_id):
    data = store.get_style(conn, style_id)
    if data is None:
        abort(404)
    return data


@bp.get("")
def list_styles():
    with _connect() as conn:
        return render_template("specs/styles.html", styles=store.list_styles(conn))


@bp.post("")
def create_style():
    form = request.form
    sizes = [s.strip() for s in form.get("sizes", "").split(",") if s.strip()]
    with _connect() as conn:
        try:
            style_id = store.create_style(
                conn, form.get("code", "").strip(), form.get("name", "").strip(),
                sizes, form.get("base_size", "").strip(),
            )
        except (GradingError, sqlite3.IntegrityError) as error:
            return render_template(
                "specs/styles.html", styles=store.list_styles(conn),
                error=_message(error), form=form,
            ), 400
    return redirect(url_for("specs.show_style", style_id=style_id))


@bp.get("/<int:style_id>")
def show_style(style_id):
    with _connect() as conn:
        return render_template("specs/style.html", **_style_or_404(conn, style_id))


@bp.post("/<int:style_id>/poms")
def add_pom(style_id):
    form = request.form
    with _connect() as conn:
        data = _style_or_404(conn, style_id)
        try:
            store.add_point_of_measure(
                conn, style_id, form.get("code", "").strip(), form.get("description", "").strip(),
                cm_to_mm(form.get("base_value_cm", "")), cm_to_mm(form.get("tolerance_cm", "")),
            )
        except (ValueError, sqlite3.IntegrityError) as error:
            return render_template("specs/style.html", **data, error=_message(error)), 400
    return redirect(url_for("specs.show_style", style_id=style_id))


@bp.post("/<int:style_id>/poms/<int:pom_id>/rules")
def set_rules(style_id, pom_id):
    with _connect() as conn:
        data = _style_or_404(conn, style_id)
        if pom_id not in data["rules"]:
            abort(404)
        try:
            # Parse every field before writing any, so one bad cell saves nothing.
            increments = {
                size["label"]: cm_to_mm(request.form[f"inc_{size['label']}"])
                for size in data["sizes"][1:]
                if request.form.get(f"inc_{size['label']}", "").strip()
            }
            for label, increment_mm in increments.items():
                store.set_grade_rule(conn, pom_id, label, increment_mm)
        except ValueError as error:
            return render_template("specs/style.html", **data, error=_message(error)), 400
    return redirect(url_for("specs.show_style", style_id=style_id))


@bp.post("/<int:style_id>/delete")
def delete_style(style_id):
    with _connect() as conn:
        if not store.delete_style(conn, style_id):
            abort(404)
    return redirect(url_for("specs.list_styles"))


def _message(error):
    if isinstance(error, sqlite3.IntegrityError):
        return "That code is already used."
    return str(error)