"""Reusable helpers for enriching FastAPI schemas with realistic examples."""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_msg_example(
    *,
    target: str,
    intent: str,
    input_payload: Dict[str, Any],
    summary: str,
    description: Optional[str] = None,
    origin: str = "swagger-ui",
) -> Dict[str, Any]:
    """Build an OpenAPI example entry for BIOwerk message envelopes."""
    example: Dict[str, Any] = {
        "summary": summary,
        "value": {
            "origin": origin,
            "target": target,
            "intent": intent,
            "input": input_payload,
            "api_version": "v1",
        },
    }

    if description:
        example["description"] = description

    return example


def build_request_body_examples(examples: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap request examples in OpenAPI-compliant structure."""
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": examples,
                }
            }
        }
    }
