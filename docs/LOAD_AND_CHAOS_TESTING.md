# Load & Chaos Testing Playbook

Use this guide to stress BIOwerk under real-world production conditions. It focuses on Mesh/Matrix routing, agent resilience, and backup/restore drills on a fresh cluster.

## Objectives
- Validate throughput and latency targets for mesh routing and each agent.
- Prove failover and back-pressure behaviors under resource exhaustion.
- Exercise disaster recovery from backups on a clean cluster.

## Prerequisites
- Deployed stack (docker-compose, Kubernetes, or bare-metal).
- Telemetry enabled (OTEL/Prometheus/Grafana) and log shipping online.
- Access to Redis (rate limiter, distributed health), Postgres, and object storage for backups.

## Load Testing (Happy Path)

1. **Baseline smoke**  
   - Warm the mesh and agents with demo payloads: `python examples/run_demo_requests.py --repeat 3`.
   - Confirm `/health` and `/ready` endpoints are green.

2. **Sustained throughput** (k6 example)  
   ```bash
   k6 run --vus 50 --duration 10m \
     --env MESH_URL=http://mesh:8000 \
     scripts/k6/mesh-sustained.js  # create if needed using docs/OPENAPI_AND_TRY_IT.md payloads
   ```
   - Track p50/p95 latencies per endpoint.
   - Watch Redis, Postgres, and CPU/memory saturation; scale replicas if queues grow.

3. **Mixed workloads**  
   - Combine nucleus plan requests, osteon drafts, myocyte ingests, and synapse storyboard generations.
   - Target a realistic RPS mix (e.g., 40% read, 60% write).

## Chaos Experiments

| Failure | How to Induce | Expected Behavior | Validate |
| --- | --- | --- | --- |
| Agent outage | Kill an agent pod/compose service | Mesh circuit breaker opens; retries limited by `retry_max_attempts` | 503 with retry hints; health dashboard flags agent |
| Slow downstream | Inject latency (e.g., `toxiproxy` or `tc netem`) | Bulkhead caps concurrency; retries back off | Latency capped, no resource starvation |
| Redis unavailable | Stop Redis or deny traffic | Rate limiting disabled gracefully; health checks degrade | Mesh logs warnings; alerts fire |
| CPU/memory pressure | Limit container resources | Bulkhead and queueing protect mesh; autoscaler adds replicas | No crash loops; p95 stable after scaling |

Capture evidence (logs, Grafana snapshots) for each experiment and record remediation steps.

## Resource Exhaustion Safeguards

- Confirm `bulkhead_max_concurrent` and `bulkhead_queue_size` values are sized per agent.
- Ensure circuit breaker thresholds (`circuit_breaker_failure_rate_threshold`, `window_size`) match SLOs.
- Monitor rate-limit 429s to distinguish user throttling from internal saturation.

## Backup & Restore Drill (Fresh Cluster)

1. **Take a backup** using the documented process (see `docs/BACKUP_QUICKSTART.md`).
2. **Provision a new environment** (fresh cluster or namespace) with the same version of BIOwerk.
3. **Restore** databases, object storage artifacts, and configuration secrets.
4. **Verify**:
   - Mesh and agents start cleanly (no stale instance IDs).
   - OpenAPI snapshots match deployed code (regenerate via `python scripts/export_openapi_snapshots.py` if needed).
   - Demo payloads succeed end-to-end.
5. **Document gaps** (missing secrets, migrations) and patch the runbook.

## Reporting

- Summarize RPS, latency, error rates, and saturation points.
- File tickets for regressions with links to Grafana panels and alert timelines.
- Include chaos findings and DR drill outcomes in the release checklist.
