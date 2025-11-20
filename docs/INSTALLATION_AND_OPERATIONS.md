# Installation and Operations Guide

This guide provides a single place to install, start, observe, and maintain BIOwerk across deployment options. Use it alongside the service-specific docs in `docs/` for deeper details.

## Prerequisites

- **Python 3.10+** for native installation
- **Docker + docker-compose** for containerized deployments
- **GNU Make** (optional) for developer workflows
- **OpenSSL** (or similar) for TLS certificate management

## Unified Control Script

`scripts/biowerkctl.sh` centralizes installation and operational commands.

```bash
./scripts/biowerkctl.sh help
```

### Install Dependencies (Native)

Create a fresh virtual environment and install dependencies:

```bash
# Production-grade dependencies
./scripts/biowerkctl.sh install

# Include developer toolchain (linters, type-checkers, tests)
./scripts/biowerkctl.sh install --dev

# Recreate the environment from scratch
./scripts/biowerkctl.sh install --force-venv
```

### Docker Operations

Manage the full stack with consistent docker-compose commands:

```bash
# Start all services (Postgres, MongoDB, Redis, Mesh gateway, agents)
./scripts/biowerkctl.sh docker-up

# Tail container logs (optional: scope to one service)
./scripts/biowerkctl.sh docker-logs          # all services
./scripts/biowerkctl.sh docker-logs mesh     # just the gateway

# Rebuild everything after config or dependency changes
./scripts/biowerkctl.sh docker-rebuild

# Stop the stack cleanly
./scripts/biowerkctl.sh docker-down
```

### Health and Diagnostics

Run packaged health checks to verify liveness and configuration:

```bash
./scripts/biowerkctl.sh health-check
```

For additional observability, see:
- [MONITORING_AND_ALERTING.md](MONITORING_AND_ALERTING.md)
- [SERVICE_MESH_RESILIENCE.md](SERVICE_MESH_RESILIENCE.md)
- [AUDIT_LOGGING.md](AUDIT_LOGGING.md)

### Cleanup

Reset local artifacts and virtual environments:

```bash
./scripts/biowerkctl.sh clean
```

## Installation Path Reference

- **Portable tarball**: `distribution/portable/README.md`
- **Docker Compose**: Root `README.md` quick start and `docker-compose.yml`
- **Desktop installers**: `distribution/README.md`
- **Kubernetes/Helm**: `k8s/` and `helm/` directories
- **Database bootstrap**: `DATABASE.md`, `alembic/`, and Makefile migration targets

## Service-Specific Usage

Each service exposes typed FastAPI endpoints. Quick examples:

- **Mesh gateway docs**: http://localhost:8080/docs
- **Osteon draft**: `curl -X POST http://localhost:8080/v1/osteon/draft -H 'Content-Type: application/json' -d @examples/osteon_draft.json`
- **Myocyte analysis**: `curl -X POST http://localhost:8080/v1/myocyte/analyze -H 'Content-Type: application/json' -d @examples/myocyte_analyze.json`
- **Synapse slide**: `curl -X POST http://localhost:8080/v1/synapse/render -H 'Content-Type: application/json' -d @examples/synapse_render.json`

See `examples/` for ready-to-run payloads.

## Operations Playbook

- **Security**: `docs/SECURITY.md`, `AUTH.md`, `AUDIT_LOGGING_IMPLEMENTATION.md`, and `scripts/security_scan.py`
- **Data Protection**: `docs/DATA_RETENTION.md`, `docs/gdpr_compliance.md`
- **Disaster Recovery**: `docs/BACKUP_QUICKSTART.md`, `docs/DISASTER_RECOVERY.md`
- **Scaling**: `docs/SCALING.md`, `docs/SERVICE_MESH_RESILIENCE.md`

Follow these alongside the control script to keep deployments consistent, observable, and recoverable.
