from __future__ import annotations

import argparse
import asyncio
import json
import socket
import subprocess
import sys
import time
import urllib.request

import websockets


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_get(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _wait_for_endpoint(url: str, *, expected_status: str, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, payload = _http_get(url)
            if status == 200 and payload.get("status") == expected_status:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Endpoint did not become ready: {url} ({last_error})")


async def _websocket_ping(ws_url: str, token: str) -> None:
    async with websockets.connect(
        ws_url,
        additional_headers={"X-API-Key": token},
        open_timeout=10,
        close_timeout=5,
    ) as websocket:
        await websocket.send("ping")
        payload = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))
        if payload != {"type": "pong"}:
            raise RuntimeError(f"Unexpected websocket payload: {payload}")


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-rollout Kubernetes smoke check")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--remote-port", type=int, default=80)
    parser.add_argument("--local-port", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--context", default="")
    args = parser.parse_args()

    kubectl_base = ["kubectl"]
    if args.context:
        kubectl_base.extend(["--context", args.context])

    _run(
        kubectl_base
        + [
            "rollout",
            "status",
            f"deployment/{args.deployment}",
            "-n",
            args.namespace,
            f"--timeout={int(args.timeout_seconds)}s",
        ]
    )

    local_port = args.local_port or _free_port()
    port_forward = subprocess.Popen(
        kubectl_base
        + [
            "port-forward",
            f"svc/{args.service}",
            f"{local_port}:{args.remote_port}",
            "-n",
            args.namespace,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base_url = f"http://127.0.0.1:{local_port}"
    ws_url = f"ws://127.0.0.1:{local_port}/ws/signals"

    try:
        _wait_for_endpoint(
            f"{base_url}/health/live",
            expected_status="alive",
            timeout_seconds=args.timeout_seconds,
        )
        _wait_for_endpoint(
            f"{base_url}/health/ready",
            expected_status="ready",
            timeout_seconds=args.timeout_seconds,
        )
        status, payload = _http_get(f"{base_url}/", headers={"X-API-Key": args.token})
        if status != 200 or payload.get("status") != "running":
            raise RuntimeError(f"Unexpected authenticated root response: {status} {payload}")
        asyncio.run(_websocket_ping(ws_url, args.token))
        print("Kubernetes post-deploy smoke check passed")
        return 0
    except Exception as exc:
        print(f"Kubernetes post-deploy smoke check failed: {exc}", file=sys.stderr)
        return 1
    finally:
        port_forward.terminate()
        try:
            port_forward.wait(timeout=10)
        except subprocess.TimeoutExpired:
            port_forward.kill()
            port_forward.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
