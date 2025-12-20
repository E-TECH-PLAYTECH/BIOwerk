from __future__ import annotations

import hashlib
import json
from importlib import import_module
from pathlib import Path
import types
from typing import Dict
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
SNAPSHOT_DIR = ROOT / "docs" / "openapi-snapshots"

# Map service name to module path
TARGETS: Dict[str, str] = {
    "mesh": "mesh.main",
    "osteon": "services.osteon.main",
    "myocyte": "services.myocyte.main",
    "synapse": "services.synapse.main",
    "circadian": "services.circadian.main",
    "nucleus": "services.nucleus.main",
    "chaperone": "services.chaperone.main",
}


def _install_blake3_stub() -> None:
    """Provide a minimal blake3 stub when the native package is unavailable.

    This keeps OpenAPI generation working in constrained environments without
    altering production dependencies.
    """
    if "blake3" in sys.modules:
        return

    module = types.ModuleType("blake3")

    def blake3(data: bytes = b""):
        hasher = hashlib.blake2s()
        hasher.update(data)
        return hasher

    module.blake3 = blake3
    sys.modules["blake3"] = module


def _install_pymongo_stub() -> None:
    """Provide lightweight pymongo stubs for documentation generation."""
    if "pymongo" in sys.modules:
        return

    pymongo_module = types.ModuleType("pymongo")
    pymongo_errors = types.ModuleType("pymongo.errors")
    pymongo_errors.ConfigurationError = Exception

    pymongo_cursor = types.ModuleType("pymongo.cursor")
    pymongo_cursor._QUERY_OPTIONS = None  # type: ignore[attr-defined]
    pymongo_cursor.Cursor = type("Cursor", (), {})
    pymongo_cursor.RawBatchCursor = type("RawBatchCursor", (), {})

    pymongo_module.errors = pymongo_errors
    pymongo_module.cursor = pymongo_cursor

    sys.modules["pymongo"] = pymongo_module
    sys.modules["pymongo.errors"] = pymongo_errors
    sys.modules["pymongo.cursor"] = pymongo_cursor


def _install_motor_stub() -> None:
    """Provide a minimal motor stub to avoid optional dependency issues."""
    if "motor" in sys.modules:
        return

    motor_module = types.ModuleType("motor")
    motor_asyncio = types.ModuleType("motor.motor_asyncio")

    class AsyncIOMotorClient:  # pragma: no cover - test helper
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    motor_asyncio.AsyncIOMotorClient = AsyncIOMotorClient
    motor_module.motor_asyncio = motor_asyncio

    sys.modules["motor"] = motor_module
    sys.modules["motor.motor_asyncio"] = motor_asyncio


def _install_prometheus_stub() -> None:
    """Provide a no-op Prometheus instrumentator stub."""
    if "prometheus_fastapi_instrumentator" in sys.modules:
        return

    module = types.ModuleType("prometheus_fastapi_instrumentator")

    class Instrumentator:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def instrument(self, app=None, **_kwargs):
            return self

        def expose(self, app=None, **_kwargs):
            return self

    module.Instrumentator = Instrumentator
    sys.modules["prometheus_fastapi_instrumentator"] = module


def _install_structlog_stub() -> None:
    """Provide a lightweight structlog stub."""
    if "structlog" in sys.modules:
        return

    module = types.ModuleType("structlog")

    class _Logger:
        def bind(self, **_kwargs):
            return self

        def info(self, *args, **kwargs):
            return self

        def warning(self, *args, **kwargs):
            return self

        def error(self, *args, **kwargs):
            return self

        def debug(self, *args, **kwargs):
            return self

    def get_logger(*_args, **_kwargs):
        return _Logger()

    module.get_logger = get_logger
    sys.modules["structlog"] = module


def _install_llm_stubs() -> None:
    """Provide stubs for optional LLM SDKs (openai, anthropic, ollama)."""
    if "openai" not in sys.modules:
        openai_module = types.ModuleType("openai")

        class AsyncOpenAI:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def __getattr__(self, _name):
                async def _noop(*_args, **_kwargs):
                    return {}
                return _noop

        openai_module.AsyncOpenAI = AsyncOpenAI
        sys.modules["openai"] = openai_module

    if "anthropic" not in sys.modules:
        anthropic_module = types.ModuleType("anthropic")

        class AsyncAnthropic:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def __getattr__(self, _name):
                async def _noop(*_args, **_kwargs):
                    return {}
                return _noop

        anthropic_module.AsyncAnthropic = AsyncAnthropic
        sys.modules["anthropic"] = anthropic_module

    if "ollama" not in sys.modules:
        ollama_module = types.ModuleType("ollama")

        class AsyncClient:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            async def generate(self, *args, **kwargs):
                return {"output": ""}

        ollama_module.AsyncClient = AsyncClient
        sys.modules["ollama"] = ollama_module


def load_app(module_path: str):
    module = import_module(module_path)
    app = getattr(module, "app", None)
    if app is None:
        raise AttributeError(f"Module {module_path} does not expose an 'app' FastAPI instance")
    return app


def export_snapshot(service: str, module_path: str) -> Path:
    app = load_app(module_path)
    spec = app.openapi()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    outfile = SNAPSHOT_DIR / f"{service}.json"
    outfile.write_text(json.dumps(spec, indent=2))
    return outfile


def main() -> None:
    _install_blake3_stub()
    _install_pymongo_stub()
    _install_motor_stub()
    _install_prometheus_stub()
    _install_structlog_stub()
    _install_llm_stubs()
    exported = []
    for service, module_path in TARGETS.items():
        outfile = export_snapshot(service, module_path)
        exported.append(outfile)
        print(f"[ok] {service} -> {outfile.relative_to(ROOT)}")

    print(f"Exported {len(exported)} OpenAPI snapshot(s) to {SNAPSHOT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
