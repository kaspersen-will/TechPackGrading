"""A stand-in for the specs service: a real HTTP server on a free local port.

The samples service talks to it exactly as it talks to specs (real sockets,
real timeouts), but each test decides what it answers. Its responses follow
GET /styles/{id}/spec/{size} in services/specs/openapi.yaml.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

# Chest 54.0 cm at L, tolerance 1.0 cm: what specs returns for JK-014 size L.
SPEC_L = {
    "style_code": "JK-014",
    "poms": [{"pom_id": 1, "code": "CH", "description": "Chest", "target_mm": 540,
              "tolerance_mm": 10}],
}


class StubSpecs:
    def __init__(self):
        self.status, self.body, self.delay_s, self.requests = 200, SPEC_L, 0, []

    def answer(self, status, body=None, delay_s=0):
        self.status, self.body, self.delay_s = status, body, delay_s


def _handler(stub):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            stub.requests.append(self.path)
            time.sleep(stub.delay_s)
            payload = stub.body if isinstance(stub.body, bytes) else json.dumps(stub.body).encode()
            self.send_response(stub.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):  # keep test output quiet
            pass
    return Handler


@pytest.fixture
def specs():
    """Yields (stub, base_url). The server stops when the test ends."""
    stub = StubSpecs()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(stub))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                              daemon=True)
    thread.start()
    yield stub, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def nothing_listening():
    """A base URL where no server listens: what samples sees when specs is stopped."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = server.server_port
    server.server_close()
    return f"http://127.0.0.1:{port}"
