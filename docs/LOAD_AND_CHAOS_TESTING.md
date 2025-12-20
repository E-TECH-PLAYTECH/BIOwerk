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

4. **Targeted gateway & Matrix suites**  
   - Mesh gateway: run per-route load with distributed tracing enabled; assert SLOs (p50 ≤ 150 ms, p95 ≤ 400 ms, error rate < 0.5%).  
   - Matrix service bundles: focus on inter-service routing and fan-out; ensure concurrency pools do not exceed configured `bulkhead_max_concurrent`.  
   - Capture: RPS, latencies, non-2xx response codes, queue depth, retry volume, and circuit-breaker open/close counts.

5. **Agent-level drills**  
   - For each agent (nucleus, osteon, myocyte, synapse), run request families that stress their hottest code paths (ingest, validate, generate).  
   - Gate on per-agent SLOs (p50 ≤ 200 ms, p95 ≤ 500 ms, error rate < 1%).  
   - Capture downstream dependency timings (DB, Redis, external APIs) to attribute regressions.

6. **Test data and isolation**  
   - Use fixture datasets and idempotent payloads; avoid cross-test interference by isolating tenants/namespaces.  
   - Ensure rate-limiters are configured for test identities so retries and throttling can be attributed correctly.

## Chaos Experiments

| Failure | How to Induce | Expected Behavior | Validate |
| --- | --- | --- | --- |
| Agent outage | Kill an agent pod/compose service | Mesh circuit breaker opens; retries limited by `retry_max_attempts` | 503 with retry hints; health dashboard flags agent |
| Slow downstream | Inject latency (e.g., `toxiproxy` or `tc netem`) | Bulkhead caps concurrency; retries back off | Latency capped, no resource starvation |
| Redis unavailable | Stop Redis or deny traffic | Rate limiting disabled gracefully; health checks degrade | Mesh logs warnings; alerts fire |
| CPU/memory pressure | Limit container resources | Bulkhead and queueing protect mesh; autoscaler adds replicas | No crash loops; p95 stable after scaling |

Capture evidence (logs, Grafana snapshots) for each experiment and record remediation steps.

### Additional failure drills

- **Postgres outage**: stop the primary or block port 5432. Expect transaction retries to back off and read paths to surface cached responses where safe. Verify connection poolers shed load and recover without leaking idle connections.  
- **Mongo outage** (for agents using document storage): block traffic to the Mongo service. Confirm read-only paths degrade gracefully and write paths surface 503 with retry headers; ensure circuit-breaker closes after health recovers.  
- **Network partition**: apply network policies or `tc netem` to isolate a subset of pods from mesh/Matrix for 5–10 minutes. Validate partial availability—healthy shards continue serving—and that partitioned nodes resync without manual cache flush.  
- **Resource exhaustion**: throttle CPU/memory on mesh and at least one agent. Confirm autoscaling events, back-pressure via 429/503, and that queues drain after limits are lifted.  
- **Redis eviction/flush simulation**: force-evict cache keys for rate limits and session state. Verify re-priming behavior and alerting for elevated miss rates.

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

## Backup & Restore Runbook (Fresh Cluster, End-to-End)

1. **Prepare snapshot**  
   - Run `python scripts/backup.py --all --output s3://<bucket>/<ts>/` or the Helm job in `helm/backup-job.yaml`.  
   - Record the git SHA, image tags, and schema versions embedded in the backup metadata.

2. **Provision new environment**  
   - Create a clean namespace/cluster with identical mesh/agent versions and secrets (pull from Vault/secret manager).  
   - Deploy manifests/Helm charts with backup restore hooks enabled; pause autoscalers during restore to avoid churn.

3. **Restore data**  
   - Datastores: restore Postgres (pg_restore), Redis snapshots (if used), and Mongo dumps.  
   - Artifacts: sync object storage blobs (models, uploads) to the new bucket/prefix; rehydrate OpenAPI snapshots if packaged.  
   - Config: apply feature flags, rate limits, and routing tables to match source environment.

4. **Validate integrity and readiness**  
   - Run `python scripts/verify_backup_integrity.py --snapshot s3://<bucket>/<ts>/ --mode full` to compare checksums and row counts.  
   - Execute canary flows: demo payloads, matrix routing fan-out, and agent-specific CRUD paths.  
   - Confirm `/health`, `/ready`, and mesh/agent dependency health dashboards are green; ensure circuit breakers are closed.

5. **Document and handoff**  
   - Capture start/end timestamps, restore duration, and any manual steps taken.  
   - Record alert noise and remediation steps; open tickets for automation gaps.  
   - Store the runbook execution log alongside the backup metadata for traceability.
