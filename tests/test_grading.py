import pytest

from specs.grading import GradingError, grade, validate_size_run

# Chest, sizes XS=0 S=1 M=2 L=3 XL=4, base M = 520 mm.
# Uneven: XS->S is 15 mm, L->XL is 25 mm.
CHEST = {1: 15, 2: 20, 3: 20, 4: 25}


@pytest.mark.parametrize(
    "target_position, expected",
    [(0, 485), (1, 500), (2, 520), (3, 540), (4, 565)],
)
def test_grade_uneven_run_up_and_down(target_position, expected):
    assert grade(520, 2, target_position, CHEST) == expected


def test_grade_missing_rule_going_up():
    with pytest.raises(GradingError, match="position 4"):
        grade(520, 2, 4, {3: 20})


def test_grade_missing_rule_going_down():
    with pytest.raises(GradingError, match="position 1"):
        grade(520, 2, 0, {2: 20})


def test_grade_base_size_needs_no_rules():
    assert grade(520, 2, 2, {}) == 520


def test_size_run_valid():
    validate_size_run(["S", "M", "L"], "M")


@pytest.mark.parametrize(
    "sizes, base_size, message",
    [
        ([], "M", "at least one"),
        (["S", "M", "M"], "M", "twice"),
        (["S", "M", "L"], "XL", "not in the size run"),
    ],
)
def test_size_run_invalid(sizes, base_size, message):
    with pytest.raises(GradingError, match=message):
        validate_size_run(sizes, base_size)