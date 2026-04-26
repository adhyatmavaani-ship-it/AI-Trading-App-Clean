from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml


METRIC_LINE_RE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?P<labels>\{[^}]*\})?\s+(?P<value>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)$"
)
LABEL_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


@dataclass(frozen=True)
class MetricSnapshot:
    total_requests: float = 0.0
    error_requests: float = 0.0
    latency_sum_seconds: float = 0.0
    latency_count: float = 0.0
    trade_total: float = 0.0
    trade_success: float = 0.0
    portfolio_gross_exposure_pct: float = 0.0
    portfolio_max_symbol_exposure_pct: float = 0.0
    portfolio_max_theme_exposure_pct: float = 0.0
    portfolio_max_cluster_exposure_pct: float = 0.0
    portfolio_max_beta_bucket_exposure_pct: float = 0.0
    portfolio_gross_exposure_drift_pct: float = 0.0
    portfolio_cluster_concentration_drift_pct: float = 0.0
    portfolio_beta_bucket_concentration_drift_pct: float = 0.0
    portfolio_cluster_turnover: float = 0.0
    portfolio_factor_sleeve_budget_turnover: float = 0.0
    portfolio_max_factor_sleeve_budget_gap_pct: float = 0.0


@dataclass(frozen=True)
class CanaryEvaluation:
    total_requests: float
    error_rate: float
    avg_latency_ms: float
    trade_total: float
    trade_success_rate: float
    portfolio_gross_exposure_pct: float
    portfolio_max_symbol_exposure_pct: float
    portfolio_max_theme_exposure_pct: float
    portfolio_max_cluster_exposure_pct: float
    portfolio_max_beta_bucket_exposure_pct: float
    portfolio_gross_exposure_drift_pct: float
    portfolio_cluster_concentration_drift_pct: float
    portfolio_beta_bucket_concentration_drift_pct: float
    portfolio_cluster_turnover: float
    portfolio_factor_sleeve_budget_turnover: float
    portfolio_max_factor_sleeve_budget_gap_pct: float
    healthy: bool
    reasons: tuple[str, ...]


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a YAML object")
    return payload


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(command: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def _http_request(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, response.read().decode("utf-8")


def _parse_metrics(payload: str) -> MetricSnapshot:
    total_requests = 0.0
    error_requests = 0.0
    latency_sum_seconds = 0.0
    latency_count = 0.0
    trade_total = 0.0
    trade_success = 0.0
    portfolio_gross_exposure_pct = 0.0
    portfolio_max_symbol_exposure_pct = 0.0
    portfolio_max_theme_exposure_pct = 0.0
    portfolio_max_cluster_exposure_pct = 0.0
    portfolio_max_beta_bucket_exposure_pct = 0.0
    portfolio_gross_exposure_drift_pct = 0.0
    portfolio_cluster_concentration_drift_pct = 0.0
    portfolio_beta_bucket_concentration_drift_pct = 0.0
    portfolio_cluster_turnover = 0.0
    portfolio_factor_sleeve_budget_turnover = 0.0
    portfolio_max_factor_sleeve_budget_gap_pct = 0.0

    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = METRIC_LINE_RE.match(line)
        if not match:
            continue
        name = match.group("name")
        labels_blob = match.group("labels") or ""
        labels = dict(LABEL_RE.findall(labels_blob))
        value = float(match.group("value"))

        if name == "api_requests_total":
            total_requests += value
            if str(labels.get("status_code", "")).startswith("5"):
                error_requests += value
        elif name == "api_request_latency_seconds_sum":
            latency_sum_seconds += value
        elif name == "api_request_latency_seconds_count":
            latency_count += value
        elif name == "trading_executions_total":
            trade_total += value
            if str(labels.get("status", "")).upper() == "SUCCESS":
                trade_success += value
        elif name == "portfolio_gross_exposure_pct":
            portfolio_gross_exposure_pct = value
        elif name == "portfolio_max_symbol_exposure_pct":
            portfolio_max_symbol_exposure_pct = value
        elif name == "portfolio_max_theme_exposure_pct":
            portfolio_max_theme_exposure_pct = value
        elif name == "portfolio_max_cluster_exposure_pct":
            portfolio_max_cluster_exposure_pct = value
        elif name == "portfolio_max_beta_bucket_exposure_pct":
            portfolio_max_beta_bucket_exposure_pct = value
        elif name == "portfolio_gross_exposure_drift_pct":
            portfolio_gross_exposure_drift_pct = value
        elif name == "portfolio_cluster_concentration_drift_pct":
            portfolio_cluster_concentration_drift_pct = value
        elif name == "portfolio_beta_bucket_concentration_drift_pct":
            portfolio_beta_bucket_concentration_drift_pct = value
        elif name == "portfolio_cluster_turnover":
            portfolio_cluster_turnover = value
        elif name == "portfolio_factor_sleeve_budget_turnover":
            portfolio_factor_sleeve_budget_turnover = value
        elif name == "portfolio_max_factor_sleeve_budget_gap_pct":
            portfolio_max_factor_sleeve_budget_gap_pct = value

    return MetricSnapshot(
        total_requests=total_requests,
        error_requests=error_requests,
        latency_sum_seconds=latency_sum_seconds,
        latency_count=latency_count,
        trade_total=trade_total,
        trade_success=trade_success,
        portfolio_gross_exposure_pct=portfolio_gross_exposure_pct,
        portfolio_max_symbol_exposure_pct=portfolio_max_symbol_exposure_pct,
        portfolio_max_theme_exposure_pct=portfolio_max_theme_exposure_pct,
        portfolio_max_cluster_exposure_pct=portfolio_max_cluster_exposure_pct,
        portfolio_max_beta_bucket_exposure_pct=portfolio_max_beta_bucket_exposure_pct,
        portfolio_gross_exposure_drift_pct=portfolio_gross_exposure_drift_pct,
        portfolio_cluster_concentration_drift_pct=portfolio_cluster_concentration_drift_pct,
        portfolio_beta_bucket_concentration_drift_pct=portfolio_beta_bucket_concentration_drift_pct,
        portfolio_cluster_turnover=portfolio_cluster_turnover,
        portfolio_factor_sleeve_budget_turnover=portfolio_factor_sleeve_budget_turnover,
        portfolio_max_factor_sleeve_budget_gap_pct=portfolio_max_factor_sleeve_budget_gap_pct,
    )


def _diff_snapshot(before: MetricSnapshot, after: MetricSnapshot) -> MetricSnapshot:
    return MetricSnapshot(
        total_requests=max(after.total_requests - before.total_requests, 0.0),
        error_requests=max(after.error_requests - before.error_requests, 0.0),
        latency_sum_seconds=max(after.latency_sum_seconds - before.latency_sum_seconds, 0.0),
        latency_count=max(after.latency_count - before.latency_count, 0.0),
        trade_total=max(after.trade_total - before.trade_total, 0.0),
        trade_success=max(after.trade_success - before.trade_success, 0.0),
        portfolio_gross_exposure_pct=after.portfolio_gross_exposure_pct,
        portfolio_max_symbol_exposure_pct=after.portfolio_max_symbol_exposure_pct,
        portfolio_max_theme_exposure_pct=after.portfolio_max_theme_exposure_pct,
        portfolio_max_cluster_exposure_pct=after.portfolio_max_cluster_exposure_pct,
        portfolio_max_beta_bucket_exposure_pct=after.portfolio_max_beta_bucket_exposure_pct,
        portfolio_gross_exposure_drift_pct=after.portfolio_gross_exposure_drift_pct,
        portfolio_cluster_concentration_drift_pct=after.portfolio_cluster_concentration_drift_pct,
        portfolio_beta_bucket_concentration_drift_pct=after.portfolio_beta_bucket_concentration_drift_pct,
        portfolio_cluster_turnover=after.portfolio_cluster_turnover,
        portfolio_factor_sleeve_budget_turnover=after.portfolio_factor_sleeve_budget_turnover,
        portfolio_max_factor_sleeve_budget_gap_pct=after.portfolio_max_factor_sleeve_budget_gap_pct,
    )


def _evaluate_canary(delta: MetricSnapshot, analysis: dict) -> CanaryEvaluation:
    total_requests = delta.total_requests
    error_rate = delta.error_requests / total_requests if total_requests else 0.0
    avg_latency_ms = (delta.latency_sum_seconds / delta.latency_count) * 1000 if delta.latency_count else 0.0
    trade_total = delta.trade_total
    trade_success_rate = delta.trade_success / trade_total if trade_total else 1.0

    reasons: list[str] = []

    minimum_request_samples = int(analysis.get("minimumRequestSamples", 0))
    minimum_trade_samples = int(analysis.get("minimumTradeSamples", 0))
    max_error_rate = float(analysis["maxErrorRate"])
    min_trade_success_rate = float(analysis["minTradeSuccessRate"])
    max_latency_ms = float(analysis["maxLatencyMs"])
    max_gross_exposure_pct = float(analysis.get("maxGrossExposurePct", 1.0))
    max_symbol_exposure_pct = float(analysis.get("maxSymbolExposurePct", 1.0))
    max_theme_exposure_pct = float(analysis.get("maxThemeExposurePct", 1.0))
    max_cluster_exposure_pct = float(analysis.get("maxClusterExposurePct", 1.0))
    max_beta_bucket_exposure_pct = float(analysis.get("maxBetaBucketExposurePct", 1.0))
    max_gross_exposure_drift_pct = float(analysis.get("maxGrossExposureDriftPct", 1.0))
    max_cluster_concentration_drift_pct = float(analysis.get("maxClusterConcentrationDriftPct", 1.0))
    max_beta_bucket_concentration_drift_pct = float(analysis.get("maxBetaBucketConcentrationDriftPct", 1.0))
    max_cluster_turnover = float(analysis.get("maxClusterTurnover", 1.0))
    max_factor_sleeve_budget_turnover = float(analysis.get("maxFactorSleeveBudgetTurnover", 1.0))
    max_factor_sleeve_budget_gap_pct = float(analysis.get("maxFactorSleeveBudgetGapPct", 1.0))

    if total_requests < minimum_request_samples:
        reasons.append(f"insufficient request samples {int(total_requests)} < {minimum_request_samples}")
    if error_rate > max_error_rate:
        reasons.append(f"error rate {error_rate:.4f} > {max_error_rate:.4f}")
    if delta.latency_count and avg_latency_ms > max_latency_ms:
        reasons.append(f"latency {avg_latency_ms:.2f}ms > {max_latency_ms:.2f}ms")
    if trade_total < minimum_trade_samples:
        reasons.append(f"insufficient trade samples {int(trade_total)} < {minimum_trade_samples}")
    elif trade_total and trade_success_rate < min_trade_success_rate:
        reasons.append(f"trade success rate {trade_success_rate:.4f} < {min_trade_success_rate:.4f}")
    if delta.portfolio_gross_exposure_pct > max_gross_exposure_pct:
        reasons.append(f"gross exposure {delta.portfolio_gross_exposure_pct:.4f} > {max_gross_exposure_pct:.4f}")
    if delta.portfolio_max_symbol_exposure_pct > max_symbol_exposure_pct:
        reasons.append(f"symbol concentration {delta.portfolio_max_symbol_exposure_pct:.4f} > {max_symbol_exposure_pct:.4f}")
    if delta.portfolio_max_theme_exposure_pct > max_theme_exposure_pct:
        reasons.append(f"theme concentration {delta.portfolio_max_theme_exposure_pct:.4f} > {max_theme_exposure_pct:.4f}")
    if delta.portfolio_max_cluster_exposure_pct > max_cluster_exposure_pct:
        reasons.append(f"cluster concentration {delta.portfolio_max_cluster_exposure_pct:.4f} > {max_cluster_exposure_pct:.4f}")
    if delta.portfolio_max_beta_bucket_exposure_pct > max_beta_bucket_exposure_pct:
        reasons.append(f"beta bucket concentration {delta.portfolio_max_beta_bucket_exposure_pct:.4f} > {max_beta_bucket_exposure_pct:.4f}")
    if delta.portfolio_gross_exposure_drift_pct > max_gross_exposure_drift_pct:
        reasons.append(f"gross exposure drift {delta.portfolio_gross_exposure_drift_pct:.4f} > {max_gross_exposure_drift_pct:.4f}")
    if delta.portfolio_cluster_concentration_drift_pct > max_cluster_concentration_drift_pct:
        reasons.append(
            f"cluster concentration drift {delta.portfolio_cluster_concentration_drift_pct:.4f} > {max_cluster_concentration_drift_pct:.4f}"
        )
    if delta.portfolio_beta_bucket_concentration_drift_pct > max_beta_bucket_concentration_drift_pct:
        reasons.append(
            f"beta bucket concentration drift {delta.portfolio_beta_bucket_concentration_drift_pct:.4f} > {max_beta_bucket_concentration_drift_pct:.4f}"
        )
    if delta.portfolio_cluster_turnover > max_cluster_turnover:
        reasons.append(f"cluster turnover {delta.portfolio_cluster_turnover:.4f} > {max_cluster_turnover:.4f}")
    if delta.portfolio_factor_sleeve_budget_turnover > max_factor_sleeve_budget_turnover:
        reasons.append(
            f"sleeve budget turnover {delta.portfolio_factor_sleeve_budget_turnover:.4f} > {max_factor_sleeve_budget_turnover:.4f}"
        )
    if delta.portfolio_max_factor_sleeve_budget_gap_pct > max_factor_sleeve_budget_gap_pct:
        reasons.append(
            f"sleeve budget gap {delta.portfolio_max_factor_sleeve_budget_gap_pct:.4f} > {max_factor_sleeve_budget_gap_pct:.4f}"
        )

    return CanaryEvaluation(
        total_requests=total_requests,
        error_rate=error_rate,
        avg_latency_ms=avg_latency_ms,
        trade_total=trade_total,
        trade_success_rate=trade_success_rate,
        portfolio_gross_exposure_pct=delta.portfolio_gross_exposure_pct,
        portfolio_max_symbol_exposure_pct=delta.portfolio_max_symbol_exposure_pct,
        portfolio_max_theme_exposure_pct=delta.portfolio_max_theme_exposure_pct,
        portfolio_max_cluster_exposure_pct=delta.portfolio_max_cluster_exposure_pct,
        portfolio_max_beta_bucket_exposure_pct=delta.portfolio_max_beta_bucket_exposure_pct,
        portfolio_gross_exposure_drift_pct=delta.portfolio_gross_exposure_drift_pct,
        portfolio_cluster_concentration_drift_pct=delta.portfolio_cluster_concentration_drift_pct,
        portfolio_beta_bucket_concentration_drift_pct=delta.portfolio_beta_bucket_concentration_drift_pct,
        portfolio_cluster_turnover=delta.portfolio_cluster_turnover,
        portfolio_factor_sleeve_budget_turnover=delta.portfolio_factor_sleeve_budget_turnover,
        portfolio_max_factor_sleeve_budget_gap_pct=delta.portfolio_max_factor_sleeve_budget_gap_pct,
        healthy=not reasons,
        reasons=tuple(reasons),
    )


def _helm_base(context: str) -> list[str]:
    command = ["helm"]
    if context:
        command.extend(["--kube-context", context])
    return command


def _kubectl_base(context: str) -> list[str]:
    command = ["kubectl"]
    if context:
        command.extend(["--context", context])
    return command


def _helm_history_revision(release_name: str, namespace: str, context: str) -> int | None:
    try:
        result = _run(
            _helm_base(context) + ["history", release_name, "--namespace", namespace, "--output", "json"],
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return None

    history = json.loads(result.stdout or "[]")
    if not history:
        return None
    return max(int(item["revision"]) for item in history)


def _extract_digest(image_ref: str) -> str | None:
    if "@sha256:" not in image_ref:
        return None
    return image_ref.split("@", 1)[1].strip()


def _current_deployment_digest(deployment: str, namespace: str, context: str) -> str | None:
    try:
        result = _run(
            _kubectl_base(context)
            + [
                "get",
                "deployment",
                deployment,
                "--namespace",
                namespace,
                "-o",
                "jsonpath={.spec.template.spec.containers[0].image}",
            ],
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return None
    return _extract_digest(result.stdout.strip())


def _rollout_status(kind: str, name: str, namespace: str, context: str, timeout_seconds: int) -> None:
    _run(
        _kubectl_base(context)
        + [
            "rollout",
            "status",
            f"{kind}/{name}",
            "--namespace",
            namespace,
            f"--timeout={timeout_seconds}s",
        ]
    )


def _helm_upgrade(
    *,
    manifest: dict,
    stable_digest: str,
    canary_enabled: bool,
    canary_digest: str = "",
    timeout_seconds: int,
) -> None:
    command = _helm_base(manifest.get("context", "")) + [
        "upgrade",
        "--install",
        manifest["release_name"],
        manifest["chart_path"],
        "--namespace",
        manifest["namespace"],
        "--create-namespace",
        "--wait",
        "--timeout",
        f"{timeout_seconds}s",
        "-f",
        manifest["values_file"],
        "--set-string",
        f"image.repository={manifest['image']['repository']}",
        "--set-string",
        f"image.digest={stable_digest}",
        "--set-string",
        f"canary.enabled={'true' if canary_enabled else 'false'}",
    ]
    if canary_enabled:
        command.extend(
            [
                "--set-string",
                f"canary.image.digest={canary_digest}",
            ]
        )
    _run(command)


def _helm_rollback(release_name: str, namespace: str, context: str, revision: int, timeout_seconds: int) -> None:
    _run(
        _helm_base(context)
        + [
            "rollback",
            release_name,
            str(revision),
            "--namespace",
            namespace,
            "--wait",
            "--timeout",
            f"{timeout_seconds}s",
        ]
    )


def _wait_ready(base_url: str, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            live_status, live_body = _http_request(f"{base_url}/health/live")
            ready_status, ready_body = _http_request(f"{base_url}/health/ready")
            if live_status == 200 and ready_status == 200 and "\"ready\"" in ready_body and "\"alive\"" in live_body:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"canary endpoint did not become ready ({last_error})")


def _capture_snapshot(base_url: str, token: str) -> MetricSnapshot:
    status, _ = _http_request(f"{base_url}/", headers={"X-API-Key": token})
    if status != 200:
        raise RuntimeError(f"unexpected authenticated root status {status}")
    _, metrics_payload = _http_request(f"{base_url}/v1/monitoring/metrics")
    return _parse_metrics(metrics_payload)


def _monitor_canary(
    *,
    namespace: str,
    service: str,
    context: str,
    token: str,
    service_port: int,
    analysis: dict,
) -> CanaryEvaluation:
    local_port = _free_port()
    port_forward = subprocess.Popen(
        _kubectl_base(context)
        + [
            "port-forward",
            f"svc/{service}",
            f"{local_port}:{service_port}",
            "--namespace",
            namespace,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{local_port}"
    try:
        _wait_ready(base_url, timeout_seconds=60.0)
        baseline = _capture_snapshot(base_url, token)
        duration_seconds = int(analysis["durationSeconds"])
        interval_seconds = int(analysis["intervalSeconds"])
        deadline = time.time() + duration_seconds
        last_snapshot = baseline
        while time.time() < deadline:
            time.sleep(interval_seconds)
            last_snapshot = _capture_snapshot(base_url, token)
        return _evaluate_canary(_diff_snapshot(baseline, last_snapshot), analysis)
    finally:
        port_forward.terminate()
        try:
            port_forward.wait(timeout=10)
        except subprocess.TimeoutExpired:
            port_forward.kill()
            port_forward.wait(timeout=5)


def _print_evaluation(evaluation: CanaryEvaluation) -> None:
    payload = {
        "healthy": evaluation.healthy,
        "error_rate": round(evaluation.error_rate, 6),
        "trade_success_rate": round(evaluation.trade_success_rate, 6),
        "latency_ms": round(evaluation.avg_latency_ms, 2),
        "gross_exposure_pct": round(evaluation.portfolio_gross_exposure_pct, 4),
        "max_symbol_exposure_pct": round(evaluation.portfolio_max_symbol_exposure_pct, 4),
        "max_theme_exposure_pct": round(evaluation.portfolio_max_theme_exposure_pct, 4),
        "max_cluster_exposure_pct": round(evaluation.portfolio_max_cluster_exposure_pct, 4),
        "max_beta_bucket_exposure_pct": round(evaluation.portfolio_max_beta_bucket_exposure_pct, 4),
        "gross_exposure_drift_pct": round(evaluation.portfolio_gross_exposure_drift_pct, 4),
        "cluster_concentration_drift_pct": round(evaluation.portfolio_cluster_concentration_drift_pct, 4),
        "beta_bucket_concentration_drift_pct": round(evaluation.portfolio_beta_bucket_concentration_drift_pct, 4),
        "cluster_turnover": round(evaluation.portfolio_cluster_turnover, 4),
        "request_samples": int(evaluation.total_requests),
        "trade_samples": int(evaluation.trade_total),
        "reasons": list(evaluation.reasons),
    }
    print(json.dumps(payload, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Perform canary rollout for the trading backend.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--github-output", default="")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = dict(_load_json(manifest_path))
    repo_root = manifest_path.parents[2]
    manifest["chart_path"] = str((repo_root / manifest["chart_path"]).resolve())
    manifest["values_file"] = str((repo_root / manifest["values_file"]).resolve())
    values_path = Path(manifest["values_file"])
    values = _load_yaml(values_path)
    canary_values = values.get("canary") or {}
    analysis = dict(canary_values.get("analysis") or {})
    context = manifest.get("context", "")
    namespace = manifest["namespace"]
    deployment = manifest["deployment"]
    service = manifest["service"]
    target_digest = manifest["image"]["digest"]
    revision_before = _helm_history_revision(manifest["release_name"], namespace, context)
    current_digest = _current_deployment_digest(deployment, namespace, context)
    service_port = int((values.get("service") or {}).get("port", 80))
    promoted = False

    def write_outputs() -> None:
        if not args.github_output:
            return
        output_path = Path(args.github_output)
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(f"rollback_revision={revision_before or ''}\n")
            handle.write(f"promotion_performed={'true' if promoted else 'false'}\n")

    try:
        if not current_digest:
            print("No existing stable deployment found; performing bootstrap full rollout.")
            _helm_upgrade(
                manifest=manifest,
                stable_digest=target_digest,
                canary_enabled=False,
                timeout_seconds=args.timeout_seconds,
            )
            _rollout_status("deployment", deployment, namespace, context, args.timeout_seconds)
            promoted = True
            write_outputs()
            return 0

        if current_digest == target_digest:
            print("Current stable deployment already matches target digest; ensuring canary resources are removed.")
            _helm_upgrade(
                manifest=manifest,
                stable_digest=target_digest,
                canary_enabled=False,
                timeout_seconds=args.timeout_seconds,
            )
            write_outputs()
            return 0

        canary_service = f"{service}-canary"
        canary_deployment = f"{deployment}-canary"

        _helm_upgrade(
            manifest=manifest,
            stable_digest=current_digest,
            canary_enabled=True,
            canary_digest=target_digest,
            timeout_seconds=args.timeout_seconds,
        )
        _rollout_status("deployment", deployment, namespace, context, args.timeout_seconds)
        _rollout_status("deployment", canary_deployment, namespace, context, args.timeout_seconds)

        evaluation = _monitor_canary(
            namespace=namespace,
            service=canary_service,
            context=context,
            token=args.token,
            service_port=service_port,
            analysis=analysis,
        )
        _print_evaluation(evaluation)

        if not evaluation.healthy:
            raise RuntimeError("canary analysis failed")

        print("Canary is healthy; promoting canary digest to stable deployment.")
        _helm_upgrade(
            manifest=manifest,
            stable_digest=target_digest,
            canary_enabled=False,
            timeout_seconds=args.timeout_seconds,
        )
        _rollout_status("deployment", deployment, namespace, context, args.timeout_seconds)
        promoted = True
        write_outputs()
        return 0
    except Exception as exc:
        if revision_before is not None:
            print(f"Canary rollout failed: {exc}. Rolling back release {manifest['release_name']} to revision {revision_before}.")
            try:
                _helm_rollback(manifest["release_name"], namespace, context, revision_before, args.timeout_seconds)
                _rollout_status("deployment", deployment, namespace, context, args.timeout_seconds)
            except Exception as rollback_exc:
                print(f"Automatic rollback also failed: {rollback_exc}", file=sys.stderr)
        else:
            print(f"Canary rollout failed before a rollback point was available: {exc}", file=sys.stderr)
        write_outputs()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
