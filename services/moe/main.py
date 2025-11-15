"""
MOE - The Orchestrator Stooge
"Why I oughta..." - Moe tells everyone what to do

Routes and orchestrates requests between services.
Handles multi-service workflows and coordinates execution.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path
from llama_cpp import Llama
import httpx
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Moe - Orchestrator Stooge")

# Load PHI2 model
MODEL_PATH = Path("./models/phi2/model.gguf")
llm = None

# Service registry
SERVICES = {
    "osteon": "http://osteon:8001",
    "synapse": "http://synapse:8003",
    "myocyte": "http://myocyte:8002",
    "nucleus": "http://nucleus:8005",
    "chaperone": "http://chaperone:8006",
    "circadian": "http://circadian:8004",
}


@app.on_event("startup")
async def load_model():
    """Load Moe's PHI2 brain on startup."""
    global llm
    if MODEL_PATH.exists():
        logger.info(f"🎭 Moe is waking up... Loading model from {MODEL_PATH}")
        llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=2048,
            n_gpu_layers=0,
            verbose=False
        )
        logger.info("🎭 Moe is ready! 'Why I oughta...'")
    else:
        logger.warning(f"⚠️  Moe's brain not found at {MODEL_PATH}")
        logger.warning("   Run: ./scripts/download-models.sh stooges")


class WorkflowRequest(BaseModel):
    """Multi-service workflow request."""
    goal: str
    context: Optional[Dict[str, Any]] = None
    services: Optional[List[str]] = None


class WorkflowPlan(BaseModel):
    """Orchestration plan created by Moe."""
    steps: List[Dict[str, Any]]
    estimated_time: Optional[int] = None
    dependencies: Optional[Dict[str, List[str]]] = None


@app.get("/health")
async def health():
    """Check if Moe is alive."""
    return {
        "status": "healthy",
        "stooge": "moe",
        "role": "orchestrator",
        "model_loaded": llm is not None,
        "catchphrase": "Why I oughta...",
        "available_services": list(SERVICES.keys())
    }


@app.post("/plan", response_model=WorkflowPlan)
async def create_workflow_plan(request: WorkflowRequest):
    """
    Create an orchestration plan for multi-service workflows.

    Example:
        "Create a blog post, schedule it, and monitor engagement" →
        [
            {step: 1, service: "osteon", action: "generate_post"},
            {step: 2, service: "circadian", action: "schedule"},
            {step: 3, service: "chaperone", action: "monitor"}
        ]
    """
    if llm is None:
        raise HTTPException(status_code=503, detail="Moe's brain not loaded. Download phi2 model first.")

    logger.info(f"🎭 Moe planning workflow: {request.goal}")

    system_prompt = f"""You are Moe, the orchestrator. You plan multi-service workflows.

Available services: {', '.join(SERVICES.keys())}

Create a workflow plan as JSON with:
- steps: array of {{step, service, action, params}}
- estimated_time: seconds
- dependencies: which steps depend on others

Respond with ONLY valid JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Plan this workflow: {request.goal}"}
    ]

    try:
        response = llm.create_chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
            response_format={"type": "json_object"}
        )

        result = response['choices'][0]['message']['content']
        logger.info(f"🎭 Moe's plan: {result}")

        import json
        parsed = json.loads(result)

        return WorkflowPlan(**parsed)

    except Exception as e:
        logger.error(f"❌ Moe failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Planning failed: {str(e)}")


@app.post("/execute")
async def execute_workflow(plan: WorkflowPlan):
    """
    Execute a workflow plan by orchestrating service calls.
    Moe calls the shots!
    """
    logger.info(f"🎭 Moe executing {len(plan.steps)} steps...")

    results = []

    for step in plan.steps:
        service = step.get("service")
        action = step.get("action")

        if service not in SERVICES:
            logger.warning(f"⚠️  Unknown service: {service}")
            continue

        url = f"{SERVICES[service]}/{action}"
        logger.info(f"🎭 Moe calling {service}: {action}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=step.get("params", {}), timeout=30.0)
                response.raise_for_status()

                results.append({
                    "step": step.get("step"),
                    "service": service,
                    "status": "success",
                    "result": response.json()
                })

                logger.info(f"✅ Step {step.get('step')} complete")

        except Exception as e:
            logger.error(f"❌ Step {step.get('step')} failed: {str(e)}")
            results.append({
                "step": step.get("step"),
                "service": service,
                "status": "failed",
                "error": str(e)
            })

    return {
        "stooge": "moe",
        "workflow_status": "completed",
        "results": results,
        "catchphrase": "That'll learn ya!"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
