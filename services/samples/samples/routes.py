"""JSON API for Sample Fit Review. Every length is integer mm; the UI converts to cm.

Recording a round is the cross-seam flow: this service asks specs for the
graded spec (specs_client), then snapshots it into its own tables (ADR-2).
Listing and showing rounds never call specs, so they keep working when
specs is down.
"""

from contextlib import closing

from flask import Blueprint, abort, current_app, jsonify, request

import db
from samples import specs_client, store
from samples.review import STAGES, SampleError

bp = Blueprint("samples", __name__, url_prefix="/rounds")

SPECS_DOWN = ("The specs service is not responding, so this round can't be checked against "
              "its spec. Nothing was saved. Recorded rounds are unaffected; try again in a minute.")


def _connect():
    return closing(db.connect(current_app.config["DATABASE_URL"]))


def _round_json(sample_round):
    recorded_at = sample_round["recorded_at"]
    if hasattr(recorded_at, "strftime"):  # DATETIME2 comes back as a naive UTC datetime
        recorded_at = recorded_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {**sample_round, "recorded_at": recorded_at}


@bp.get("")
def list_rounds():
    with _connect() as conn:
        rounds = store.list_rounds(conn)
    return jsonify([{**_round_json(item["round"]), "summary": item["summary"]} for item in rounds])


@bp.get("/<int:round_id>")
def show_round(round_id):
    with _connect() as conn:
        data = store.get_round(conn, round_id)
    if data is None:
        abort(404, f"no sample round {round_id}")
    return jsonify(round=_round_json(data["round"]), measurements=data["measurements"],
                   summary=data["summary"])


@bp.post("")
def record_round():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "the body must be a JSON object")
    style_id, size_label = body.get("style_id"), body.get("size")
    stage, measured = body.get("stage"), body.get("measured_mm")
    if isinstance(style_id, bool) or not isinstance(style_id, int):
        abort(400, "style_id must be a number")
    if not isinstance(size_label, str) or not size_label:
        abort(400, "size is required")
    if stage not in STAGES:
        abort(400, f"stage must be one of {', '.join(STAGES)}")
    if not isinstance(measured, dict) or any(
            isinstance(v, bool) or not isinstance(v, int) for v in measured.values()):
        abort(400, "measured_mm must map each point of measure code to whole mm")

    # Ask specs before opening our own connection, so a slow specs doesn't hold one open.
    # Fetched on every submit, not when the form loaded: the spec may have changed since.
    try:
        spec = specs_client.get_graded_spec(style_id, size_label,
                                            current_app.config["SPECS_URL"],
                                            current_app.config["SPECS_TIMEOUT_S"])
    except specs_client.SpecNotFound as error:
        abort(422, str(error))
    except specs_client.SpecsUnavailable as error:
        current_app.logger.warning("cross-seam call failed: %s", error)
        abort(503, SPECS_DOWN)

    with _connect() as conn:
        try:
            round_id = store.record_round(conn, style_id, size_label, stage, spec, measured)
        except SampleError as error:
            abort(400, str(error))
    return jsonify(id=round_id), 201, {"Location": f"/rounds/{round_id}"}
