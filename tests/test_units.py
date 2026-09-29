import pytest 

from units import cm_to_mm, mm_to_cm


@pytest.mark.parametrize(
    "text, expected",
    [("52.5", 525), ("52", 520), (" 61.8 ", 618), ("-1.5", -15), ("0.3", 3)],
)
def test_cm_to_mm(text, expected):
    assert cm_to_mm(text) == expected


@pytest.mark.parametrize(
    "text, message",
    [("abc", "not a number"), ("", "not a number"), ("inf", "not a number"),
     ("52.25", "more precise than 1 mm")],
)
def test_cm_to_mm_rejects(text, message):
    with pytest.raises(ValueError, match=message):
        cm_to_mm(text)


@pytest.mark.parametrize("mm, expected", [(525, "52.5"), (520, "52.0"), (-15, "-1.5"), (3, "0.3")])
def test_mm_to_cm(mm, expected):
    assert mm_to_cm(mm) == expected


def test_round_trip_is_exact_where_float_cm_was_not():
    # As REAL cm, 60.0 + 0.6 * 3 gave 61.800000000000004 and a sample
    # at 60.8 failed a 1.0 cm tolerance. In mm the same check is exact.
    spec_mm = cm_to_mm("60.0") + 3 * cm_to_mm("0.6")
    assert spec_mm == 618
    assert abs(cm_to_mm("60.8") - spec_mm) <= cm_to_mm("1.0")