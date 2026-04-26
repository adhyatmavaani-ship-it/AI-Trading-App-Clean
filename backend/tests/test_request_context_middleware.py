import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_AVAILABLE = False

if FASTAPI_AVAILABLE:
    from app.middleware.request_context import RequestContextMiddleware


class StubMonitor:
    def __init__(self):
        self.latencies = []
        self.error_count = 0

    def record_latency(self, latency_ms: float) -> None:
        self.latencies.append(latency_ms)

    def increment_error(self) -> None:
        self.error_count += 1


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed")
class RequestContextMiddlewareTest(unittest.TestCase):
    def _build_client(self):
        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)

        @app.get("/secure")
        async def secure(request: Request):
            request.state.user_id = "alice"
            return {"status": "ok"}

        @app.get("/health/live")
        async def health_live():
            return {"status": "alive"}

        return TestClient(app)

    def test_sets_response_headers_and_logs_authenticated_user(self):
        stub_monitor = StubMonitor()
        with patch("app.middleware.request_context.SystemMonitorService", return_value=stub_monitor):
            with patch("app.middleware.request_context.logger") as mock_logger:
                client = self._build_client()
                response = client.get("/secure")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["X-Correlation-ID"])
        self.assertTrue(response.headers["X-Process-Time-Ms"])
        self.assertEqual(len(stub_monitor.latencies), 1)
        mock_logger.info.assert_called_once()
        log_call = mock_logger.info.call_args
        self.assertEqual(log_call.args[0], "request_completed")
        self.assertEqual(log_call.kwargs["extra"]["context"]["user_id"], "alice")

    def test_skips_request_completed_log_for_health_probe(self):
        stub_monitor = StubMonitor()
        with patch("app.middleware.request_context.SystemMonitorService", return_value=stub_monitor):
            with patch("app.middleware.request_context.logger") as mock_logger:
                client = self._build_client()
                response = client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["X-Correlation-ID"])
        self.assertEqual(len(stub_monitor.latencies), 1)
        mock_logger.info.assert_not_called()
