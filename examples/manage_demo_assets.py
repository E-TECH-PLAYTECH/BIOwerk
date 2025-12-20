from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


ASSET_ROOT = Path(__file__).with_name("demo_assets")
DEFAULT_TARGET = Path.home() / ".biowerk" / "demo_assets"
MANIFEST_PATH = ASSET_ROOT / "manifest.json"

logger = logging.getLogger("biowerk.demo_assets")


@dataclass(frozen=True)
class DemoAsset:
    """Metadata for a single demo asset."""

    kind: str
    path: Path
    target_agent: str
    expected_use: str
    expected_output: str

    @property
    def source(self) -> Path:
        return ASSET_ROOT / self.path


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> List[DemoAsset]:
    """Load and validate the manifest describing demo assets."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    assets: List[DemoAsset] = []
    for entry in manifest.get("workloads", []):
        asset = DemoAsset(
            kind=entry["kind"],
            path=Path(entry["path"]),
            target_agent=entry["target_agent"],
            expected_use=entry["expected_use"],
            expected_output=entry["expected_output"],
        )
        if not asset.source.exists():
            raise FileNotFoundError(f"Source asset missing: {asset.source}")
        assets.append(asset)
    if not assets:
        raise ValueError("No assets defined in manifest")
    return assets


def stage_assets(target_dir: Path, assets: Iterable[DemoAsset], overwrite: bool) -> None:
    """Copy assets into a target directory for demos."""
    for asset in assets:
        destination = target_dir / asset.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not overwrite:
            logger.info("Skipping existing asset (use --overwrite): %s", destination)
            continue
        shutil.copy2(asset.source, destination)
        logger.info("Staged %s asset → %s", asset.kind, destination)


def persist_manifest(manifest_path: Path, target_dir: Path) -> None:
    """Copy the manifest alongside staged assets for downstream tooling."""
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_path, target_dir / "manifest.json")
    logger.info("Persisted manifest to %s", target_dir / "manifest.json")


def cleanup_assets(target_dir: Path) -> None:
    """Remove staged demo assets."""
    if target_dir.exists():
        shutil.rmtree(target_dir)
        logger.info("Removed staged assets at %s", target_dir)
    else:
        logger.info("No staged assets found at %s", target_dir)


def describe_assets(assets: Iterable[DemoAsset]) -> str:
    """Render a human-readable description of assets."""
    lines = []
    for asset in assets:
        lines.append(
            f"- [{asset.kind}] {asset.path} → {asset.target_agent}\n"
            f"  use: {asset.expected_use}\n"
            f"  output: {asset.expected_output}"
        )
    return "\n".join(lines)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage sanitized BIOwerk demo assets.")
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Where to stage assets (default: {DEFAULT_TARGET}).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help=f"Path to manifest.json (default: {MANIFEST_PATH}).",
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    load_cmd = subcommands.add_parser("load", help="Stage assets to the target directory.")
    load_cmd.add_argument("--overwrite", action="store_true", help="Overwrite files if they already exist.")

    cleanup_cmd = subcommands.add_parser("cleanup", help="Remove staged assets from the target directory.")
    cleanup_cmd.add_argument("--force", action="store_true", help="Skip safety checks.")

    subcommands.add_parser("show", help="Print manifest details and validation.")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        assets = load_manifest(args.manifest)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load manifest: %s", exc)
        return 1

    if args.command == "show":
        print("Manifest validated. Assets:")
        print(describe_assets(assets))
        return 0

    target_dir = args.target_dir
    if args.command == "load":
        target_dir.mkdir(parents=True, exist_ok=True)
        stage_assets(target_dir, assets, overwrite=args.overwrite)
        persist_manifest(args.manifest, target_dir)
        logger.info("Assets ready at %s", target_dir)
        return 0

    if args.command == "cleanup":
        if not args.force and not str(target_dir).startswith(str(Path.home())):
            logger.error("Refusing to delete non-home path without --force: %s", target_dir)
            return 1
        cleanup_assets(target_dir)
        return 0

    logger.error("Unsupported command: %s", args.command)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
