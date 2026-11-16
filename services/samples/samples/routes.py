"""HTTP layer for Sample Fit Review. Parses cm form input to mm, calls the store, renders.

This is the one place Domain 2 touches Domain 1, through specs_client
(get_graded_spec and SpecError). samples/store.py and samples/review.py don't
know the specs service exists.
"""

from contextlib import closing

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

import db
from samples import store
from samples.review import STAGES
from samples.specs_client import SpecError, get_graded_spec
from units import cm_to_mm

bp = Blueprint("samples", __name__, template_folder="templates", url_prefix="/samples")


def _connect():
    return closing(db.get_connection(current_app.config["DATABASE"]))


def _style_id():
    try:
        return int(request.values.get("style_id", ""))
    except ValueError:
        abort(400)


@bp.get("")
def list_rounds():
    with _connect() as conn:
        return render_template("samples/rounds.html", rounds=store.list_rounds(conn))


@bp.get("/new")
def new_round():
    style_id, size_label = _style_id(), request.args.get("size", "")
    with _connect() as conn:
        try:
            spec = get_graded_spec(style_id, size_label)
        except SpecError as error:
            return render_template("samples/rounds.html", rounds=store.list_rounds(conn),
                                   error=str(error)), 400
    return render_template("samples/new_round.html", spec=spec, style_id=style_id,
                           size_label=size_label, stages=STAGES)


@bp.post("")
def record_round():
    form = request.form
    style_id, size_label, stage = _style_id(), form.get("size", ""), form.get("stage", "")
    with _connect() as conn:
        try:
            # Fetch the spec again on submit: it may have been edited since the form loaded.
            spec = get_graded_spec(style_id, size_label)
        except SpecError as error:
            return render_template("samples/rounds.html", rounds=store.list_rounds(conn),
                                   error=str(error)), 400
        try:
            measured = {
                pom["code"]: cm_to_mm(form[f"m_{pom['code']}"])
                for pom in spec["poms"]
                if form.get(f"m_{pom['code']}", "").strip()
            }
            round_id = store.record_round(conn, style_id, size_label, stage, spec, measured)
        except ValueError as error:
            return render_template("samples/new_round.html", spec=spec, style_id=style_id,
                                   size_label=size_label, stages=STAGES, form=form,
                                   error=str(error)), 400
    return redirect(url_for("samples.show_round", round_id=round_id))


@bp.get("/<int:round_id>")
def show_round(round_id):
    with _connect() as conn:
        data = store.get_round(conn, round_id)
    if data is None:
        abort(404)
    return render_template("samples/round.html", **data)