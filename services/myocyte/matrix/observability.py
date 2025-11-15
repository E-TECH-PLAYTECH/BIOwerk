"""Shared observability helpers for FastAPI services."""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


@lru_cache(maxsize=1)
def _instrumentator() -> Instrumentator:
    """Return a cached instrumentator instance.

    Using a shared instance prevents duplicate metric registration when the
    helper is called multiple times (e.g., in tests or hot reloads).
    """

    return Instrumentator()


def setup_instrumentation(app: FastAPI) -> None:
    """Attach Prometheus metrics exposition to the given FastAPI app."""

    instrumentator = _instrumentator()
    instrumentator.instrument(app)
    instrumentator.expose(app, include_in_schema=False, endpoint="/metrics")
