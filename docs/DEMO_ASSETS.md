## Demo assets and Mesh walkthroughs

Use these sanitized assets to exercise the Mesh end-to-end without pulling production data. They map directly to document (osteon), sheet (myocyte), and slide (synapse) workloads.

### Included assets

| Kind   | Path | Target agent | Expected output |
| --- | --- | --- | --- |
| Document brief | `examples/demo_assets/docs/readiness_brief.md` | `osteon` | Outline/draft with provenance hashes and export-ready sections. |
| Reliability sheet | `examples/demo_assets/sheets/reliability_metrics.csv` | `myocyte` | Normalized table with value checks and anomaly callouts. |
| Slide narrative | `examples/demo_assets/slides/launch_review.json` | `synapse` | Storyboard with visual guidance for leadership reviews. |

The manifest at `examples/demo_assets/manifest.json` records the mapping and intended use for each file.

### Load and clean up assets

Stage the demo artifacts anywhere (defaults to `~/.biowerk/demo_assets`):

```bash
python examples/manage_demo_assets.py load --target-dir ~/.biowerk/demo_assets --overwrite
```

Inspect the manifest and asset validation:

```bash
python examples/manage_demo_assets.py show --manifest ~/.biowerk/demo_assets/manifest.json
```

Remove staged assets when done:

```bash
python examples/manage_demo_assets.py cleanup --target-dir ~/.biowerk/demo_assets --force
```

### Agent interactions and end-to-end flows

Replay sanitized payloads across drafting (osteon), analysis (myocyte), visualization (synapse), and orchestration (nucleus):

```bash
BIOWERK_MESH_URL=http://localhost:8080 python examples/mesh_agent_showcase.py --dry-run
BIOWERK_MESH_URL=http://localhost:8080 python examples/mesh_agent_showcase.py
```

Use the notebook for interactive exploration:

```
examples/notebooks/mesh_agent_walkthrough.ipynb
```

### Expected responses

- **Osteon draft**: HTTP 200 with `ok=true`, `agent="osteon"`, and `state_hash` populated for the outline/draft body.
- **Myocyte ingest**: HTTP 200 with `ok=true`, normalized table rows, and validation notes reflecting the sheet expectations.
- **Synapse storyboard**: HTTP 200 with `ok=true`, slide titles mirroring the JSON input, and visual recommendations tagged per slide.
- **Nucleus plan**: HTTP 200 with `ok=true`, indicating routing choices for osteon/myocyte/synapse plus any governance notes.

If any flow fails, the showcase script logs the label and response payload for quick debugging.
