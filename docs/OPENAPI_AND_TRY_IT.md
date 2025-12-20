# OpenAPI Snapshots & Live "Try It Now" Examples

This guide keeps BIOwerk’s API documentation synchronized across the mesh and all agents, and provides ready-to-run examples for manual validation.

## Regenerate OpenAPI/Swagger Snapshots

Use the helper script to generate fresh OpenAPI definitions for the mesh gateway and every agent service:

```bash
python scripts/export_openapi_snapshots.py
```

- Snapshots are emitted to `docs/openapi-snapshots/{service}.json`.
- Commit updated snapshots alongside API changes to preserve drift detection.
- The script imports each FastAPI app directly, so you do not need running services; ensure your virtual environment has project dependencies installed.

## Validate Snapshots

- Run a quick schema sanity check:
  ```bash
  python - <<'PY'
  import json, pathlib
  snap_dir = pathlib.Path("docs/openapi-snapshots")
  for path in snap_dir.glob("*.json"):
      data = json.loads(path.read_text())
      assert "paths" in data and data["paths"], f"Missing paths in {path}"
      print(f"{path.name}: {len(data['paths'])} paths")
  PY
  ```
- Verify versioned vs. legacy routes: mesh routes are exposed at `/v1/{agent}/{endpoint}` with legacy fallbacks preserved for compatibility.

## Live "Try It Now" Examples (Mesh)

All mesh calls share the same envelope:
```json
{
  "origin": "demo-cli",
  "target": "<agent>",
  "intent": "<endpoint>",
  "input": { "..." }
}
```

Replace `http://localhost:8080` with your mesh URL and execute:

- **Nucleus Plan**
  ```bash
  curl -X POST http://localhost:8080/v1/nucleus/plan \
    -H "Content-Type: application/json" \
    -d '{"origin":"demo-cli","target":"nucleus","intent":"plan","input":{"goal":"Plan launch readiness for Q4","requirements":["mesh health checks","artifact export"]}}'
  ```

- **Osteon Outline**
  ```bash
  curl -X POST http://localhost:8080/v1/osteon/outline \
    -H "Content-Type: application/json" \
    -d '{"origin":"demo-cli","target":"osteon","intent":"outline","input":{"goal":"Produce a one-pager on platform launch","context":"Highlight reliability and governance"}}'
  ```

- **Myocyte Ingest Table**
  ```bash
  curl -X POST http://localhost:8080/v1/myocyte/ingest_table \
    -H "Content-Type: application/json" \
    -d '{"origin":"demo-cli","target":"myocyte","intent":"ingest_table","input":{"raw_data":"region,revenue\nNA,120\nEU,98","tables":[]}}'
  ```

- **Synapse Storyboard**
  ```bash
  curl -X POST http://localhost:8080/v1/synapse/storyboard \
    -H "Content-Type: application/json" \
    -d '{"origin":"demo-cli","target":"synapse","intent":"storyboard","input":{"topic":"Launch review","audience":"executive","num_slides":5}}'
  ```

- **Circadian Timeline**
  ```bash
  curl -X POST http://localhost:8080/v1/circadian/plan_timeline \
    -H "Content-Type: application/json" \
    -d '{"origin":"demo-cli","target":"circadian","intent":"plan_timeline","input":{"project_description":"Mesh/SaaS rollout","duration_weeks":10,"team_size":6,"goals":["Harden rate limits","Ship updated desktop launcher"]}}'
  ```

- **Chaperone Import**
  ```bash
  curl -X POST http://localhost:8080/v1/chaperone/import_artifact \
    -H "Content-Type: application/json" \
    -d '{"origin":"demo-cli","target":"chaperone","intent":"import_artifact","input":{"format":"markdown","artifact_type":"osteon","content":"# BIOwerk Readiness\n- Mesh resilience\n- OpenAPI snapshots"}}'
  ```

## Try-It Automation with Samples

- Seeded demo payloads live in `examples/demo_requests.json`.
- Use `examples/run_demo_requests.py` to replay them against any mesh host:
  ```bash
  BIOWERK_MESH_URL=http://localhost:8080 python examples/run_demo_requests.py
  ```
- The script prints per-endpoint status and short summaries to verify end-to-end execution quickly.

## When to Regenerate

- Adding or modifying endpoints
- Changing request/response models
- Adjusting middleware that affects docs (e.g., auth, versioning, validation)
- Before releases to ensure `/docs` and `/openapi.json` match shipped behavior
