# Distributed Load Validation Report

Generated: 2026-04-24T19:42:43.049441+00:00

## Scenario
- Subscribers: 100000
- Signals in burst: 3
- Shards: 64
- Queue batch size: 250

## Key Metrics
- Subscription registration time: 514.24 ms
- Broadcast latency p50/p95: 788.26 / 2352.15 ms
- Total queued jobs: 136917
- Shard load mean/max: 2139.33 / 23787
- Shard imbalance ratio: 11.12
- Queue lag p50/p95/max: 1889.26 / 3253.48 / 3884.09 ms
- Delayed queue first served on cycle: 4
- Duplicate jobs observed: 0
- Approx Redis payload footprint: 47.19 MB

## Failure Simulation
- Worker crash data loss detected: True
- Redis restart data loss detected: True

## Execution Quality Model
- Expected vs modeled actual price: 100.0000 vs 100.3000
- Expected vs modeled slippage: 12.00 vs 30.00 bps

## Bottlenecks
- Signal fanout currently scans all `subscription:*` keys per publish, so broadcast cost scales linearly with subscriber count.
- Queue dequeue is destructive (`zpop_due_json`) without an ack/lease phase, so a worker crash after dequeue can lose jobs.
- Redis Pub/Sub is non-durable; a Redis restart without AOF/replication can drop in-flight signal broadcasts and queue state.
- Delayed queues remain fair in the synthetic burst run, but sustained high-priority load can still starve them because dequeue always prefers `high` then `normal` before `delayed`.

## Recommendations
- Move subscriber selection to precomputed segment indexes or Redis sets per tier/risk class to avoid full-key scans on every signal.
- Add leased queue semantics with visibility timeout and explicit ack/requeue before MICRO live scale-out.
- Enable Redis AOF + replica promotion and separate Pub/Sub from durable queue state.
- Introduce per-priority worker pools or weighted fair scheduling so delayed queues cannot starve indefinitely.
- Back HPA with queue-depth and queue-lag metrics, not just depth, to catch cold-start lag before execution quality degrades.
