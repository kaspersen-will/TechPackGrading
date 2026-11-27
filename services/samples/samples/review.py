# Pure sample fit review logic. No SQLite, no Flask, no import from specs.
# Every value is integer mm, so every comparison is exact.

STAGES = ("proto", "fit", "pre-production")


class SampleError(ValueError):
    """A sample round can't be recorded from the data given."""


def passes(target_mm, tolerance_mm, measured_mm):
    """True if the measurement is within the tolerance.

    Off by exactly the tolerance is a pass (tolerance is inclusive, ADR-3).
    """
    return abs(measured_mm - target_mm) <= tolerance_mm


def build_measurements(spec_poms, measured_by_code):
    """Pair every graded point of measure with the factory's value.

    spec_poms is the "poms" list from the graded spec. measured_by_code maps
    a POM code to the measured value in mm. The round is one submission:
    a missing or unknown code rejects the whole thing, so no row is ever
    half-filled.
    """
    if not spec_poms:
        raise SampleError("this style has no points of measure to check")

    spec_codes = {pom["code"] for pom in spec_poms}
    missing = sorted(spec_codes - measured_by_code.keys())
    if missing:
        raise SampleError(f"no measurement for {', '.join(missing)}")
    unknown = sorted(measured_by_code.keys() - spec_codes)
    if unknown:
        raise SampleError(f"{', '.join(unknown)} is not in the graded spec")

    rows = []
    for pom in spec_poms:
        measured_mm = measured_by_code[pom["code"]]
        if measured_mm <= 0:
            raise SampleError(f"{pom['code']} must be greater than zero")
        rows.append({
            "pom_code": pom["code"],
            "description": pom["description"],
            "target_mm": pom["target_mm"],
            "tolerance_mm": pom["tolerance_mm"],
            "measured_mm": measured_mm,
            # Decided now and stored with the round (migration 003), never recomputed.
            "passes": passes(pom["target_mm"], pom["tolerance_mm"], measured_mm),
        })
    return rows


def review(measurement):
    """One stored snapshot row plus its signed deviation.

    The verdict is the one stored when the round was recorded, not recomputed,
    so a later change to passes() can't change a past round's result.
    """
    return {
        **measurement,
        "deviation_mm": measurement["measured_mm"] - measurement["target_mm"],
        "passes": bool(measurement["passes"]),
    }


def summarise(reviewed):
    """Per-round summary: how many POMs failed and whether the round is approved."""
    failed = [row["pom_code"] for row in reviewed if not row["passes"]]
    return {
        "total": len(reviewed),
        "failed": len(failed),
        "failed_codes": failed,
        "approved": not failed,
    }
