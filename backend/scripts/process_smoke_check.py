from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import websockets


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_get(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body)


def _wait_for_live(url: str, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, payload = _http_get(url)
            if status == 200 and payload.get("status") == "alive":
                return
        except Exception as exc:  # pragma: no cover - exercised in CI timing windows
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Smoke server did not become healthy at {url}: {last_error}")


async def _websocket_ping(ws_url: str, token: str) -> None:
    async with websockets.connect(
        ws_url,
        additional_headers={"X-API-Key": token},
        open_timeout=5,
        close_timeout=5,
    ) as websocket:
        await websocket.send("ping")
        message = await asyncio.wait_for(websocket.recv(), timeout=5)
        payload = json.loads(message)
        if payload != {"type": "pong"}:
            raise RuntimeError(f"Unexpected websocket response: {payload}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real-process FastAPI smoke test.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", default="ci-smoke-token")
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    port = args.port or _free_port()
    base_url = f"http://{args.host}:{port}"
    ws_url = f"ws://{args.host}:{port}/ws/signals"

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(backend_dir),
            "ENVIRONMENT": env.get("ENVIRONMENT", "dev"),
            "TRADING_MODE": env.get("TRADING_MODE", "paper"),
            "JSON_LOGS": env.get("JSON_LOGS", "false"),
            "LOG_LEVEL": env.get("LOG_LEVEL", "WARNING"),
            "REDIS_URL": env.get("REDIS_URL", "redis://127.0.0.1:6399/0"),
            "FIRESTORE_PROJECT_ID": "",
            "WEBSOCKET_LISTENER_ENABLED": "false",
            "AUTH_API_KEYS_JSON": json.dumps(
                [
                    {
                        "api_key": args.token,
                        "user_id": "smoke-user",
                        "key_id": "smoke-key",
                    }
                ]
            ),
        }
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            args.host,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=backend_dir,
        env=env,
    )

    try:
        _wait_for_live(f"{base_url}/health/live", args.startup_timeout)
        status, payload = _http_get(
            f"{base_url}/",
            headers={"X-API-Key": args.token},
        )
        if status != 200 or payload.get("status") != "running":
            raise RuntimeError(f"Unexpected root response: status={status}, payload={payload}")

        asyncio.run(_websocket_ping(ws_url, args.token))
        print("FastAPI process smoke test passed")
        return 0
    except Exception as exc:
        print(f"FastAPI process smoke test failed: {exc}", file=sys.stderr)
        return 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
