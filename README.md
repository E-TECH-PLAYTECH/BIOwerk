# Bio-Themed Agentic Office Suite (CODEX scaffold)

This repository is a production-oriented scaffold for an **agentic AI app suite** using biological/physical metaphors:

- **Nucleus** (Director/orchestrator)
- **Osteon** (Document program-agent)
- **Myocyte** (Analysis/Spreadsheet program-agent)
- **Synapse** (Presentation/Visualization program-agent)
- **Circadian** (Scheduler/Workflow program-agent)
- **Chaperone** (Adapter for import/export to external formats)
- **Matrix** (shared utilities, message envelope, canonicalization)

> Native artifact formats: `.osteon`, `.myotab`, `.synslide` (simple JSON-based containers).

## Quick start

```bash
# 1) Start all services
docker compose up --build

# 2) Open gateway (Mesh) docs:
# http://localhost:8080/docs

# 3) Try a draft with Osteon (Writer analogue):
curl -X POST http://localhost:8080/osteon/draft -H 'Content-Type: application/json' -d @examples/osteon_draft.json
```

Need ongoing service insight? See [Operations](#operations) for observability and continuity guidance.

## Architecture

- Each agent is a FastAPI microservice with typed endpoints.
- JSON-RPC–style payloads with canonical JSON and BLAKE3 state hashes.
- The **Mesh gateway** exposes a unified API surface and routes messages to agents.
- **Matrix** provides shared libs for canonicalization, hashing, and message schemas.

## Determinism

All service replies include a `state_hash = blake3-256(canonical_json(output))`.
Golden tests can assert output hashes for regression checks.

## Interop

**Chaperone** handles import/export (e.g., Office formats) without creating runtime coupling.
The core suite operates entirely on native formats.

## Operations

Production deployments should plan for consistent observability and disaster recovery. The suite’s FastAPI services run as discrete containers, so the patterns below apply uniformly across Mesh and every agent.

### Log aggregation

- **Structured logs** – Each container writes access/application logs to STDOUT. To guarantee structured JSON, extend the container command with a custom logging config:

  ```yaml
  # docker-compose.override.yml
  services:
    mesh:
      command:
        - uvicorn
        - main:app
        - --host
        - 0.0.0.0
        - --port
        - "8080"
        - --log-config
        - /config/logging.json
      volumes:
        - ./ops/logging.json:/config/logging.json:ro
  ```

- **Common tooling integration** – Ship the container logs to your preferred aggregator:
  - *Grafana Loki*: add a `promtail` sidecar that follows `/var/lib/docker/containers/*/*.log` and parses JSON.
  - *ELK / OpenSearch*: run Filebeat or Vector to tail the same Docker log files and forward them with the `json` codec.
  - *Cloud logging*: configure Fluent Bit with the Docker input (`tag mesh.*`) and forward to CloudWatch, Stackdriver, or Azure Monitor.

- **Retention** – Retain at least 7 days of INFO-level logs and 30 days of WARN+/AUDIT streams to support replaying canonical `Msg`/`Reply` envelopes when investigating incidents.

### Prometheus scraping

- **Metrics endpoints** – Mesh and each agent expose Prometheus-compatible metrics at `http://<service-host>:<port>/metrics`. For a local stack you can confirm with:

  ```bash
  curl http://localhost:8080/metrics    # Mesh gateway
  curl http://localhost:8001/metrics    # Osteon agent
  ```

- **Scrape configuration** – Point Prometheus at every container (adjust the hostnames when deploying outside of Compose):

  ```yaml
  scrape_configs:
    - job_name: "bio-suite"
      metrics_path: /metrics
      static_configs:
        - targets:
            - mesh:8080
            - osteon:8001
            - myocyte:8002
            - synapse:8003
            - circadian:8004
            - nucleus:8005
            - chaperone:8006
  ```

- **Dashboards** – Import Grafana dashboards for FastAPI/Uvicorn or build panels around `http_requests_total`, `http_request_duration_seconds_*`, and custom gauges emitted by each agent.

### Alert thresholds

- **Latency** – Page when the 95th percentile of `http_request_duration_seconds` exceeds 500 ms for five consecutive minutes (higher thresholds for heavy exports).
- **Error budget** – Alert on `increase(http_requests_total{status=~"5.."}[5m]) / increase(http_requests_total[5m]) > 0.02` to keep the aggregate error rate below 2%.
- **Availability** – Track a synthetic `up` gauge per container; raise a ticket if any agent is down for longer than 60 seconds.
- **Queue pressure** – Monitor application-specific counters (for example, `osteon_drafts_in_flight`) if you add them; pair alerts with Slack / PagerDuty routes in Alertmanager.

### Backup procedures

- **Configuration snapshots** – Version-control-sensitive files (`suite.yaml`, `schemas/`, `matrix/`) already live in Git. Take weekly tarball snapshots for operations by running `tar -czf backups/suite-config-$(date +%F).tgz suite.yaml schemas matrix` from the repository root.
- **Artifact exports** – Mount a persistent host directory (e.g., `./artifacts:/data/artifacts`) in Compose so generated `.osteon`, `.myotab`, and `.synslide` files are captured. Schedule nightly rsync (or cloud storage sync) of that directory.
- **Database / external stores** – If you attach external stateful services (PostgreSQL, object storage), follow their native backup tooling and document credentials in your runbook.
- **Disaster recovery drill** – Quarterly, rebuild the stack from backups (`docker compose up --build`), replay a representative set of artifacts through Mesh, and confirm `/metrics` plus structured logging are operational.

## License

Proprietary scaffold for CODEX handoff. Replace this with your project’s license.
