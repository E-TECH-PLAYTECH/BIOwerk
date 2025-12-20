from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx


DEFAULT_DATASET = Path(__file__).with_name("demo_requests.json")


def load_requests(dataset: Path) -> Tuple[str, List[Dict[str, Any]]]:
    """Load demo request definitions."""
    if not dataset.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset}")

    data = json.loads(dataset.read_text())
    mesh_url = data.get("mesh_url", "http://localhost:8080").rstrip("/")
    requests_list = data.get("requests", [])
    if not requests_list:
        raise ValueError("No requests defined in dataset")
    return mesh_url, requests_list


def send_request(base_url: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Send a single request and capture timing."""
    path = entry["path"]
    payload = entry["payload"]
    url = f"{base_url}{path}"

    start = time.perf_counter()
    response = httpx.post(url, json=payload, timeout=30.0)
    elapsed_ms = (time.perf_counter() - start) * 1000

    summary = {
        "label": entry.get("label", path),
        "status": response.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
    }

    try:
        body = response.json()
    except ValueError:
        summary["error"] = response.text[:500]
    else:
        summary["ok"] = body.get("ok", response.ok)
        summary["agent"] = body.get("agent") or payload.get("target")
        summary["intent"] = payload.get("intent")
        summary["state_hash"] = body.get("state_hash")
        if not response.ok:
            summary["error"] = body

    return summary


def run(mesh_url: str, dataset: Path, repeat: int, focus: str) -> int:
    base_url, entries = load_requests(dataset)
    if mesh_url:
        base_url = mesh_url.rstrip("/")

    filtered = [e for e in entries if focus in e["path"] or focus in e.get("label", "")]
    if focus and not filtered:
        raise ValueError(f"No requests matched focus filter '{focus}'")
    if filtered:
        entries = filtered

    print(f"Using mesh at {base_url} with {len(entries)} request(s). Repeat={repeat}")
    failures = 0

    for _ in range(repeat):
        for entry in entries:
            try:
                result = send_request(base_url, entry)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"[FAIL] {entry.get('label', entry['path'])}: {exc}")
                continue

            status = "OK" if result.get("status", 0) < 400 else "FAIL"
            if status == "FAIL":
                failures += 1
            print(
                f"[{status}] {result.get('label')} :: "
                f"status={result.get('status')} elapsed_ms={result.get('elapsed_ms')} "
                f"agent={result.get('agent')} intent={result.get('intent')}"
            )
            if "error" in result:
                print(f"       error={result['error']}")

    return failures


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run demo mesh requests for BIOwerk.")
    parser.add_argument("--mesh-url", default="", help="Override mesh base URL (default from dataset file).")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to demo requests JSON.")
    parser.add_argument("--repeat", type=int, default=1, help="How many times to replay the dataset.")
    parser.add_argument(
        "--focus",
        default="",
        help="Optional substring to filter requests by label or path (e.g., 'osteon' or 'nucleus/plan').",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    try:
        failures = run(args.mesh_url, args.dataset, args.repeat, args.focus)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
