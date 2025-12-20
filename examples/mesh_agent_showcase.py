from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import httpx

from examples.manage_demo_assets import ASSET_ROOT, DEFAULT_TARGET, load_manifest


logger = logging.getLogger("biowerk.mesh_agent_showcase")


@dataclass
class FlowResult:
    """Captured details from a Mesh request."""

    label: str
    status: int
    elapsed_ms: float
    agent: str
    intent: str
    ok: bool
    state_hash: str | None = None
    error: str | None = None


def resolve_asset_root(preferred: Path | None) -> Path:
    """Pick the best asset root available."""
    if preferred:
        return preferred
    env_root = os.getenv("BIOWERK_DEMO_ASSETS")
    if env_root:
        candidate = Path(env_root).expanduser()
        if candidate.exists():
            return candidate
    if DEFAULT_TARGET.exists():
        return DEFAULT_TARGET
    return ASSET_ROOT


def build_flows(asset_root: Path) -> List[Dict[str, Any]]:
    """Construct Mesh-ready payloads for document, sheet, and slide scenarios."""
    doc_text = (asset_root / "docs" / "readiness_brief.md").read_text()
    sheet_csv = (asset_root / "sheets" / "reliability_metrics.csv").read_text()
    slide_json = json.loads((asset_root / "slides" / "launch_review.json").read_text())

    return [
        {
            "label": "osteon draft sanitized brief",
            "path": "/v1/osteon/draft",
            "payload": {
                "origin": "demo-cli",
                "target": "osteon",
                "intent": "draft",
                "input": {
                    "goal": "Executive-ready launch brief with reliability focus",
                    "context": doc_text,
                    "requirements": [
                        "show governance hooks for documents, sheets, and slides",
                        "include provenance tags for audit exports",
                    ],
                },
            },
        },
        {
            "label": "myocyte analyze reliability sheet",
            "path": "/v1/myocyte/ingest_table",
            "payload": {
                "origin": "demo-cli",
                "target": "myocyte",
                "intent": "ingest_table",
                "input": {
                    "raw_data": sheet_csv,
                    "tables": [],
                    "expectations": {
                        "primary_keys": ["metric"],
                        "value_checks": {"latency_p95_ms": {"max": 1200}},
                    },
                },
            },
        },
        {
            "label": "synapse storyboard visuals",
            "path": "/v1/synapse/storyboard",
            "payload": {
                "origin": "demo-cli",
                "target": "synapse",
                "intent": "storyboard",
                "input": {
                    "topic": slide_json["title"],
                    "audience": slide_json["audience"],
                    "num_slides": len(slide_json["slides"]),
                    "context": slide_json["slides"],
                    "visual_preferences": ["minimal", "accessible", "exportable"],
                },
            },
        },
        {
            "label": "nucleus orchestrates doc/sheet/slide",
            "path": "/v1/nucleus/plan",
            "payload": {
                "origin": "demo-cli",
                "target": "nucleus",
                "intent": "plan",
                "input": {
                    "goal": "Mesh-wide leadership review pack",
                    "requirements": [
                        "document draft ready for export",
                        "sheet insights summarized",
                        "slides aligned to governance themes",
                    ],
                    "available_agents": ["osteon", "myocyte", "synapse", "chaperone"],
                },
            },
        },
    ]


def send_request(base_url: str, entry: Dict[str, Any]) -> FlowResult:
    """Send a Mesh request and capture timing and state."""
    url = f"{base_url}{entry['path']}"
    payload = entry["payload"]

    start = time.perf_counter()
    response = httpx.post(url, json=payload, timeout=30.0)
    elapsed_ms = (time.perf_counter() - start) * 1000

    try:
        body = response.json()
    except ValueError:
        raise RuntimeError(f"Non-JSON response for {entry['label']}: {response.text}") from None

    return FlowResult(
        label=entry["label"],
        status=response.status_code,
        elapsed_ms=round(elapsed_ms, 2),
        agent=body.get("agent") or payload.get("target"),
        intent=payload.get("intent", ""),
        ok=body.get("ok", response.is_success),
        state_hash=body.get("state_hash"),
        error=None if response.is_success else json.dumps(body)[:500],
    )


def run_showcase(mesh_url: str, asset_root: Path, dry_run: bool) -> List[FlowResult]:
    """Execute (or print) the canonical demo flows."""
    flows = build_flows(asset_root)
    results: List[FlowResult] = []

    if dry_run:
        print("Dry-run only. Payloads prepared for inspection:")
        print(json.dumps({"mesh_url": mesh_url, "requests": flows}, indent=2))
        return results

    for entry in flows:
        try:
            result = send_request(mesh_url, entry)
        except Exception as exc:  # noqa: BLE001
            logger.error("Flow %s failed: %s", entry["label"], exc)
            results.append(
                FlowResult(
                    label=entry["label"],
                    status=0,
                    elapsed_ms=0.0,
                    agent=entry["payload"]["target"],
                    intent=entry["payload"].get("intent", ""),
                    ok=False,
                    error=str(exc),
                )
            )
            continue
        status_label = "OK" if result.ok and result.status < 400 else "FAIL"
        logger.info(
            "[%s] %s → agent=%s intent=%s status=%s elapsed_ms=%.2f",
            status_label,
            result.label,
            result.agent,
            result.intent,
            result.status,
            result.elapsed_ms,
        )
        results.append(result)
    return results


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay end-to-end Mesh flows with sanitized assets.")
    parser.add_argument(
        "--mesh-url",
        default=None,
        help="Mesh base URL (default: BIOWERK_MESH_URL env or http://localhost:8080).",
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=None,
        help="Path to staged assets. Defaults to $BIOWERK_DEMO_ASSETS or repo demo_assets.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending them to the Mesh.",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    mesh_url = (args.mesh_url or os.getenv("BIOWERK_MESH_URL") or "http://localhost:8080").rstrip("/")

    asset_root = resolve_asset_root(args.asset_root)
    manifest_path = asset_root / "manifest.json"
    if manifest_path.exists():
        try:
            load_manifest(manifest_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Asset validation failed at %s: %s", asset_root, exc)
            return 1
    else:
        logger.warning("Manifest not found at %s; continuing without validation.", manifest_path)

    results = run_showcase(mesh_url, asset_root, args.dry_run)
    failures = [r for r in results if not r.ok]
    if failures:
        logger.error("Completed with %s failure(s).", len(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
