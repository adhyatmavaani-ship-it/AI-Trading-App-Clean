from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RolloutEvaluation:
    error_rate: float
    trade_success_rate: float
    latency_ms: float
    gross_exposure_pct: float
    max_symbol_exposure_pct: float
    max_theme_exposure_pct: float
    max_cluster_exposure_pct: float
    max_beta_bucket_exposure_pct: float
    gross_exposure_drift_pct: float
    cluster_concentration_drift_pct: float
    beta_bucket_concentration_drift_pct: float
    cluster_turnover: float
    factor_sleeve_budget_turnover: float
    max_factor_sleeve_budget_gap_pct: float
    request_samples: float
    trade_samples: float
    healthy: bool
    reasons: tuple[str, ...]
    active_alerts: tuple[str, ...]


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a YAML object")
    return payload


def _run(command: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=capture_output, text=True)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _kubectl_base(context: str) -> list[str]:
    command = ["kubectl"]
    if context:
        command.extend(["--context", context])
    return command


def _helm_base(context: str) -> list[str]:
    command = ["helm"]
    if context:
        command.extend(["--kube-context", context])
    return command


def _query_prometheus(base_url: str, query: str) -> float:
    url = f"{base_url}/api/v1/query?{urllib.parse.urlencode({'query': query})}"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    result = payload.get("data", {}).get("result", [])
    if not result:
        return 0.0
    return float(result[0]["value"][1])


def _active_rollout_alerts(base_url: str, *, namespace: str, release_name: str, alert_names: list[str]) -> tuple[str, ...]:
    with urllib.request.urlopen(f"{base_url}/api/v2/alerts", timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    active: list[str] = []
    allowed = set(alert_names)
    for alert in payload:
        if alert.get("status", {}).get("state") != "active":
            continue
        labels = alert.get("labels", {})
        if labels.get("namespace") != namespace:
            continue
        if labels.get("release_name") != release_name:
            continue
        alert_name = labels.get("alertname", "")
        if alert_name in allowed:
            active.append(alert_name)
    return tuple(sorted(set(active)))


def _prometheus_queries(namespace: str, release_name: str, lookback: str) -> dict[str, str]:
    selector = f'namespace="{namespace}",app_kubernetes_io_instance="{release_name}",rollout_track="stable"'
    return {
        "request_total": f"sum(increase(api_requests_total{{{selector}}}[{lookback}]))",
        "request_error": f'sum(increase(api_requests_total{{{selector},status_code=~"5.."}}[{lookback}]))',
        "latency_sum": f"sum(increase(api_request_latency_seconds_sum{{{selector}}}[{lookback}]))",
        "latency_count": f"sum(increase(api_request_latency_seconds_count{{{selector}}}[{lookback}]))",
        "trade_total": f"sum(increase(trading_executions_total{{{selector}}}[{lookback}]))",
        "trade_success": f'sum(increase(trading_executions_total{{{selector},status="SUCCESS"}}[{lookback}]))',
        "gross_exposure": f'max_over_time(portfolio_gross_exposure_pct{{{selector}}}[{lookback}])',
        "max_symbol_exposure": f'max_over_time(portfolio_max_symbol_exposure_pct{{{selector}}}[{lookback}])',
        "max_theme_exposure": f'max_over_time(portfolio_max_theme_exposure_pct{{{selector}}}[{lookback}])',
        "max_cluster_exposure": f'max_over_time(portfolio_max_cluster_exposure_pct{{{selector}}}[{lookback}])',
        "max_beta_bucket_exposure": f'max_over_time(portfolio_max_beta_bucket_exposure_pct{{{selector}}}[{lookback}])',
        "gross_exposure_drift": f'max_over_time(portfolio_gross_exposure_drift_pct{{{selector}}}[{lookback}])',
        "cluster_concentration_drift": f'max_over_time(portfolio_cluster_concentration_drift_pct{{{selector}}}[{lookback}])',
        "beta_bucket_concentration_drift": f'max_over_time(portfolio_beta_bucket_concentration_drift_pct{{{selector}}}[{lookback}])',
        "cluster_turnover": f'max_over_time(portfolio_cluster_turnover{{{selector}}}[{lookback}])',
        "factor_sleeve_budget_turnover": f'max_over_time(portfolio_factor_sleeve_budget_turnover{{{selector}}}[{lookback}])',
        "max_factor_sleeve_budget_gap_pct": f'max_over_time(portfolio_max_factor_sleeve_budget_gap_pct{{{selector}}}[{lookback}])',
    }


def _evaluate_snapshot(metrics: dict[str, float], analysis: dict, active_alerts: tuple[str, ...]) -> RolloutEvaluation:
    request_samples = metrics["request_total"]
    trade_samples = metrics["trade_total"]
    error_rate = metrics["request_error"] / request_samples if request_samples else 0.0
    trade_success_rate = metrics["trade_success"] / trade_samples if trade_samples else 1.0
    latency_ms = (metrics["latency_sum"] / metrics["latency_count"]) * 1000 if metrics["latency_count"] else 0.0

    reasons: list[str] = []
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
    if request_samples < int(analysis["minimumRequestSamples"]):
        reasons.append(
            f"insufficient request samples {int(request_samples)} < {int(analysis['minimumRequestSamples'])}"
        )
    if error_rate > float(analysis["maxErrorRate"]):
        reasons.append(f"error rate {error_rate:.4f} > {float(analysis['maxErrorRate']):.4f}")
    if metrics["latency_count"] and latency_ms > float(analysis["maxLatencyMs"]):
        reasons.append(f"latency {latency_ms:.2f}ms > {float(analysis['maxLatencyMs']):.2f}ms")
    if trade_samples < int(analysis["minimumTradeSamples"]):
        reasons.append(f"insufficient trade samples {int(trade_samples)} < {int(analysis['minimumTradeSamples'])}")
    elif trade_success_rate < float(analysis["minTradeSuccessRate"]):
        reasons.append(
            f"trade success rate {trade_success_rate:.4f} < {float(analysis['minTradeSuccessRate']):.4f}"
        )
    if metrics["gross_exposure"] > max_gross_exposure_pct:
        reasons.append(f"gross exposure {metrics['gross_exposure']:.4f} > {max_gross_exposure_pct:.4f}")
    if metrics["max_symbol_exposure"] > max_symbol_exposure_pct:
        reasons.append(f"symbol concentration {metrics['max_symbol_exposure']:.4f} > {max_symbol_exposure_pct:.4f}")
    if metrics["max_theme_exposure"] > max_theme_exposure_pct:
        reasons.append(f"theme concentration {metrics['max_theme_exposure']:.4f} > {max_theme_exposure_pct:.4f}")
    if metrics["max_cluster_exposure"] > max_cluster_exposure_pct:
        reasons.append(f"cluster concentration {metrics['max_cluster_exposure']:.4f} > {max_cluster_exposure_pct:.4f}")
    if metrics["max_beta_bucket_exposure"] > max_beta_bucket_exposure_pct:
        reasons.append(f"beta bucket concentration {metrics['max_beta_bucket_exposure']:.4f} > {max_beta_bucket_exposure_pct:.4f}")
    if metrics["gross_exposure_drift"] > max_gross_exposure_drift_pct:
        reasons.append(f"gross exposure drift {metrics['gross_exposure_drift']:.4f} > {max_gross_exposure_drift_pct:.4f}")
    if metrics["cluster_concentration_drift"] > max_cluster_concentration_drift_pct:
        reasons.append(
            f"cluster concentration drift {metrics['cluster_concentration_drift']:.4f} > {max_cluster_concentration_drift_pct:.4f}"
        )
    if metrics["beta_bucket_concentration_drift"] > max_beta_bucket_concentration_drift_pct:
        reasons.append(
            f"beta bucket concentration drift {metrics['beta_bucket_concentration_drift']:.4f} > {max_beta_bucket_concentration_drift_pct:.4f}"
        )
    if metrics["cluster_turnover"] > max_cluster_turnover:
        reasons.append(f"cluster turnover {metrics['cluster_turnover']:.4f} > {max_cluster_turnover:.4f}")
    if metrics["factor_sleeve_budget_turnover"] > max_factor_sleeve_budget_turnover:
        reasons.append(
            f"sleeve budget turnover {metrics['factor_sleeve_budget_turnover']:.4f} > {max_factor_sleeve_budget_turnover:.4f}"
        )
    if metrics["max_factor_sleeve_budget_gap_pct"] > max_factor_sleeve_budget_gap_pct:
        reasons.append(
            f"sleeve budget gap {metrics['max_factor_sleeve_budget_gap_pct']:.4f} > {max_factor_sleeve_budget_gap_pct:.4f}"
        )
    if active_alerts and bool(analysis.get("rollbackOnAlert", True)):
        reasons.append(f"alertmanager active alerts: {', '.join(active_alerts)}")

    return RolloutEvaluation(
        error_rate=error_rate,
        trade_success_rate=trade_success_rate,
        latency_ms=latency_ms,
        gross_exposure_pct=float(metrics["gross_exposure"]),
        max_symbol_exposure_pct=float(metrics["max_symbol_exposure"]),
        max_theme_exposure_pct=float(metrics["max_theme_exposure"]),
        max_cluster_exposure_pct=float(metrics["max_cluster_exposure"]),
        max_beta_bucket_exposure_pct=float(metrics["max_beta_bucket_exposure"]),
        gross_exposure_drift_pct=float(metrics["gross_exposure_drift"]),
        cluster_concentration_drift_pct=float(metrics["cluster_concentration_drift"]),
        beta_bucket_concentration_drift_pct=float(metrics["beta_bucket_concentration_drift"]),
        cluster_turnover=float(metrics["cluster_turnover"]),
        factor_sleeve_budget_turnover=float(metrics["factor_sleeve_budget_turnover"]),
        max_factor_sleeve_budget_gap_pct=float(metrics["max_factor_sleeve_budget_gap_pct"]),
        request_samples=request_samples,
        trade_samples=trade_samples,
        healthy=not reasons,
        reasons=tuple(reasons),
        active_alerts=active_alerts,
    )


def _monitor_post_promotion(
    *,
    prometheus_url: str,
    alertmanager_url: str,
    namespace: str,
    release_name: str,
    analysis: dict,
) -> RolloutEvaluation:
    end_time = time.time() + int(analysis["durationSeconds"])
    interval = int(analysis["intervalSeconds"])
    lookback = str(analysis["lookbackWindow"])
    last_evaluation: RolloutEvaluation | None = None

    while time.time() < end_time:
        queries = _prometheus_queries(namespace, release_name, lookback)
        metrics = {name: _query_prometheus(prometheus_url, query) for name, query in queries.items()}
        active_alerts = _active_rollout_alerts(
            alertmanager_url,
            namespace=namespace,
            release_name=release_name,
            alert_names=list(analysis["alertNames"]),
        )
        last_evaluation = _evaluate_snapshot(metrics, analysis, active_alerts)
        print(
            json.dumps(
                {
                    "healthy": last_evaluation.healthy,
                    "error_rate": round(last_evaluation.error_rate, 6),
                    "trade_success_rate": round(last_evaluation.trade_success_rate, 6),
                    "latency_ms": round(last_evaluation.latency_ms, 2),
                    "gross_exposure_pct": round(last_evaluation.gross_exposure_pct, 4),
                    "max_symbol_exposure_pct": round(last_evaluation.max_symbol_exposure_pct, 4),
                    "max_theme_exposure_pct": round(last_evaluation.max_theme_exposure_pct, 4),
                    "max_cluster_exposure_pct": round(last_evaluation.max_cluster_exposure_pct, 4),
                    "max_beta_bucket_exposure_pct": round(last_evaluation.max_beta_bucket_exposure_pct, 4),
                    "gross_exposure_drift_pct": round(last_evaluation.gross_exposure_drift_pct, 4),
                    "cluster_concentration_drift_pct": round(last_evaluation.cluster_concentration_drift_pct, 4),
                    "beta_bucket_concentration_drift_pct": round(last_evaluation.beta_bucket_concentration_drift_pct, 4),
                    "cluster_turnover": round(last_evaluation.cluster_turnover, 4),
                    "request_samples": int(last_evaluation.request_samples),
                    "trade_samples": int(last_evaluation.trade_samples),
                    "active_alerts": list(last_evaluation.active_alerts),
                    "reasons": list(last_evaluation.reasons),
                },
                indent=2,
            )
        )
        if not last_evaluation.healthy:
            return last_evaluation
        time.sleep(interval)

    if last_evaluation is None:
        raise RuntimeError("post-promotion monitoring could not collect any samples")
    return last_evaluation


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


def _rollout_status(deployment: str, namespace: str, context: str, timeout_seconds: int) -> None:
    _run(
        _kubectl_base(context)
        + [
            "rollout",
            "status",
            f"deployment/{deployment}",
            "--namespace",
            namespace,
            f"--timeout={timeout_seconds}s",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor post-promotion rollout health and auto-rollback on degradation.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--rollback-revision", default="")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = dict(_load_json(manifest_path))
    repo_root = manifest_path.parents[2]
    manifest["values_file"] = str((repo_root / manifest["values_file"]).resolve())
    values = _load_yaml(Path(manifest["values_file"]))
    monitoring = values.get("rolloutMonitoring") or {}
    if not monitoring.get("enabled", True):
        print("Post-promotion monitoring is disabled; skipping.")
        return 0

    context = manifest.get("context", "")
    namespace = manifest["namespace"]
    release_name = manifest["release_name"]
    deployment = manifest["deployment"]
    analysis = dict(monitoring["analysis"])
    prometheus = dict(monitoring["prometheus"])
    alertmanager = dict(monitoring["alertmanager"])

    prom_local_port = _free_port()
    am_local_port = _free_port()
    prom_pf = subprocess.Popen(
        _kubectl_base(context)
        + [
            "port-forward",
            f"svc/{prometheus['serviceName']}",
            f"{prom_local_port}:{int(prometheus['port'])}",
            "--namespace",
            prometheus["namespace"],
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    am_pf = subprocess.Popen(
        _kubectl_base(context)
        + [
            "port-forward",
            f"svc/{alertmanager['serviceName']}",
            f"{am_local_port}:{int(alertmanager['port'])}",
            "--namespace",
            alertmanager["namespace"],
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    prometheus_url = f"http://127.0.0.1:{prom_local_port}"
    alertmanager_url = f"http://127.0.0.1:{am_local_port}"

    try:
        evaluation = _monitor_post_promotion(
            prometheus_url=prometheus_url,
            alertmanager_url=alertmanager_url,
            namespace=namespace,
            release_name=release_name,
            analysis=analysis,
        )
        if evaluation.healthy:
            print("Post-promotion monitoring window completed without degradation.")
            return 0

        if not args.rollback_revision:
            print(
                "Post-promotion degradation detected but no rollback revision was provided.",
                file=sys.stderr,
            )
            return 1

        rollback_revision = int(args.rollback_revision)
        print(
            f"Post-promotion degradation detected. Rolling back release {release_name} to revision {rollback_revision}."
        )
        _helm_rollback(release_name, namespace, context, rollback_revision, args.timeout_seconds)
        _rollout_status(deployment, namespace, context, args.timeout_seconds)
        return 1
    finally:
        for process in (prom_pf, am_pf):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
