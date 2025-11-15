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

## License

Proprietary scaffold for CODEX handoff. Replace this with your project’s license.
