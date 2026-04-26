# Distributed Load Testing

This folder contains the high-concurrency validation bundle for the Redis-backed signal fanout and execution queue layer.

## Files

- `distributed_load_validation.py`
  Runs a local synthetic 100,000-user-equivalent benchmark with in-memory Redis semantics and writes JSON/Markdown reports.
- `locustfile.py`
  Runs a real Redis-backed load test for subscription fanout, signal publishing, and shard dequeue throughput.
- `reports/`
  Stores generated benchmark output.

## Local Synthetic Validation

```bash
python infrastructure/loadtest/distributed_load_validation.py
```

This produces:

- `infrastructure/loadtest/reports/distributed-load-report.json`
- `infrastructure/loadtest/reports/distributed-load-report.md`

## Real Redis / Cluster Validation

Install Locust in the environment used for load generation:

```bash
pip install locust
```

Run the load test against the target Redis/backend environment:

```bash
locust -f infrastructure/loadtest/locustfile.py --headless --users 100000 --spawn-rate 1500 --run-time 10m
```

## What To Watch

- Signal publish latency
- Queue depth by shard
- Queue lag from enqueue to dequeue
- Redis memory growth
- Duplicate or lost jobs during worker crashes
- HPA scale-up delay relative to queue growth
