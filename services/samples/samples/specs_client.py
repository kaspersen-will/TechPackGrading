"""The seam: the only place the samples service reaches the specs service.

GET {SPECS_URL}/styles/<id>/spec/<size> over HTTP, with a timeout. Returns
{"style_code": str, "poms": [{pom_id, code, description, target_mm, tolerance_mm}, ...]},
the same shape specs.store.get_graded_spec returned inside the monolith.
Standard library only, so no extra dependency.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

# Ignore HTTP(S)_PROXY from the environment: the call goes straight to SPECS_URL.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class SpecError(Exception):
    """The graded spec could not be obtained."""


class SpecNotFound(SpecError):
    """Specs answered: no such style or size, or the spec can't be graded yet."""


class SpecsUnavailable(SpecError):
    """Specs didn't answer in time, couldn't be reached, or failed (5xx)."""


def get_graded_spec(style_id, size_label, base_url, timeout_s):
    url = "{}/styles/{}/spec/{}".format(
        base_url.rstrip("/"), int(style_id), urllib.parse.quote(size_label, safe=""))
    try:
        # timeout covers connecting and each read, so a hung specs can't hang this request.
        with _opener.open(url, timeout=timeout_s) as response:
            spec = json.load(response)
    except urllib.error.HTTPError as error:  # specs answered, with an error status
        if error.code in (404, 422):
            raise SpecNotFound(_error_message(error)) from None
        raise SpecsUnavailable(f"specs answered {error.code}") from None
    except (urllib.error.URLError, OSError, ValueError) as error:  # refused, timeout, bad JSON
        raise SpecsUnavailable(f"specs did not answer: {error}") from None
    if not isinstance(spec, dict) or not isinstance(spec.get("poms"), list):
        raise SpecsUnavailable("specs answered with an unexpected body")
    return spec


def _error_message(error):
    try:
        return json.load(error)["error"]
    except (ValueError, KeyError, TypeError):
        return f"specs answered {error.code}"
