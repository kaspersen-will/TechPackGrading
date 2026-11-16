import pytest

from samples.review import SampleError, build_measurements, passes, review, summarise

CHEST = {"code": "CH", "description": "Chest", "target_mm": 520, "tolerance_mm": 10}
LENGTH = {"code": "BL", "description": "Body length", "target_mm": 720, "tolerance_mm": 15}


def test_inside_tolerance_passes():
    assert passes(520, 10, 529)
    assert passes(520, 10, 511)


def test_exactly_at_tolerance_passes():
    assert passes(520, 10, 530)
    assert passes(520, 10, 510)


def test_one_mm_past_tolerance_fails():
    assert not passes(520, 10, 531)
    assert not passes(520, 10, 509)


def test_build_measurements_snapshots_spec_values():
    rows = build_measurements([CHEST, LENGTH], {"CH": 525, "BL": 700})
    assert rows[0] == {"pom_code": "CH", "description": "Chest", "target_mm": 520,
                       "tolerance_mm": 10, "measured_mm": 525}
    assert rows[1]["measured_mm"] == 700


def test_missing_measurement_rejects_whole_round():
    with pytest.raises(SampleError, match="no measurement for BL"):
        build_measurements([CHEST, LENGTH], {"CH": 525})


def test_unknown_code_rejects_whole_round():
    with pytest.raises(SampleError, match="SL is not in the graded spec"):
        build_measurements([CHEST], {"CH": 525, "SL": 600})


def test_non_positive_measurement_rejected():
    with pytest.raises(SampleError, match="greater than zero"):
        build_measurements([CHEST], {"CH": 0})


def test_spec_without_poms_rejected():
    with pytest.raises(SampleError, match="no points of measure"):
        build_measurements([], {})


def test_review_adds_signed_deviation_and_verdict():
    row = review({"pom_code": "CH", "description": "Chest", "target_mm": 520,
                  "tolerance_mm": 10, "measured_mm": 505})
    assert row["deviation_mm"] == -15
    assert row["passes"] is False


def test_summary_counts_failures():
    reviewed = [{"pom_code": "CH", "passes": True}, {"pom_code": "BL", "passes": False}]
    assert summarise(reviewed) == {"total": 2, "failed": 1, "failed_codes": ["BL"],
                                   "approved": False}


def test_summary_all_pass_is_approved():
    assert summarise([{"pom_code": "CH", "passes": True}])["approved"] is True