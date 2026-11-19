"""specs_client against a stub specs over real HTTP. No database needed."""

import time

import pytest
from stub_specs import SPEC_L, nothing_listening, specs  # noqa: F401 (fixtures)

from samples.specs_client import SpecNotFound, SpecsUnavailable, get_graded_spec


def test_returns_the_graded_spec(specs):  # noqa: F811
    stub, url = specs
    assert get_graded_spec(1, "L", url, timeout_s=2) == SPEC_L
    assert stub.requests == ["/styles/1/spec/L"]


def test_size_label_is_escaped_in_the_path(specs):  # noqa: F811
    stub, url = specs
    get_graded_spec(1, "W32/L34", url, timeout_s=2)
    assert stub.requests == ["/styles/1/spec/W32%2FL34"]


@pytest.mark.parametrize("status", [404, 422])
def test_specs_saying_no_is_not_found_with_its_message(specs, status):  # noqa: F811
    stub, url = specs
    stub.answer(status, {"error": "style 1 has no size 'XXL'"})
    with pytest.raises(SpecNotFound, match="has no size 'XXL'"):
        get_graded_spec(1, "XXL", url, timeout_s=2)


def test_specs_failing_is_unavailable(specs):  # noqa: F811
    stub, url = specs
    stub.answer(503, {"status": "unavailable"})
    with pytest.raises(SpecsUnavailable):
        get_graded_spec(1, "L", url, timeout_s=2)


def test_specs_stopped_is_unavailable(nothing_listening):  # noqa: F811
    with pytest.raises(SpecsUnavailable):
        get_graded_spec(1, "L", nothing_listening, timeout_s=2)


def test_slow_specs_times_out_instead_of_hanging(specs):  # noqa: F811
    stub, url = specs
    stub.answer(200, SPEC_L, delay_s=2)
    started = time.monotonic()
    with pytest.raises(SpecsUnavailable):
        get_graded_spec(1, "L", url, timeout_s=0.3)
    assert time.monotonic() - started < 1.5


def test_garbage_body_is_unavailable(specs):  # noqa: F811
    stub, url = specs
    stub.answer(200, b"<html>gateway error</html>")
    with pytest.raises(SpecsUnavailable):
        get_graded_spec(1, "L", url, timeout_s=2)
