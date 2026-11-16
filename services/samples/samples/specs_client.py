"""The seam: the only place the samples service reaches the specs service.

Replaces the direct import of specs.store.get_graded_spec. Same return shape:
{"style_code": str, "poms": [{pom_id, code, description, target_mm, tolerance_mm}, ...]}.
Stub for now; it becomes an HTTP call with a timeout to SPECS_URL.
"""


class SpecError(Exception):
    """The graded spec could not be obtained: unknown style/size, or specs unreachable."""


def get_graded_spec(style_id, size_label):
    raise SpecError("the specs service is not connected yet")
