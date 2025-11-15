from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os, httpx, time
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
from matrix.logging_config import setup_logging, log_request, log_response, log_error
from matrix.errors import AgentNotFoundError

app = FastAPI(title="Mesh Gateway")
setup_instrumentation(app)
logger = setup_logging("mesh")

AGENT_URLS = {
    "osteon": os.getenv("AGENT_OSTEON_URL","http://osteon:8001"),
    "myocyte": os.getenv("AGENT_MYOCYTE_URL","http://myocyte:8002"),
    "synapse": os.getenv("AGENT_SYNAPSE_URL","http://synapse:8003"),
    "circadian": os.getenv("AGENT_CIRCADIAN_URL","http://circadian:8004"),
    "nucleus": os.getenv("AGENT_NUCLEUS_URL","http://nucleus:8005"),
    "chaperone": os.getenv("AGENT_CHAPERONE_URL","http://chaperone:8006"),
}

@app.post("/{agent}/{endpoint}")
async def route(agent: str, endpoint: str, request: Request):
    start_time = time.time()
    data = await request.json()
    msg = Msg(**data)

    log_request(logger, msg.id, agent, endpoint)

    target_base = AGENT_URLS.get(agent)
    if not target_base:
        error = AgentNotFoundError(f"Unknown agent: {agent}", {"agent": agent, "available_agents": list(AGENT_URLS.keys())})
        log_error(logger, msg.id, error, agent=agent, endpoint=endpoint)
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent}")

    url = f"{target_base}/{endpoint}"
    headers = {}
    auth_header = request.headers.get("authorization")
    if auth_header:
        headers["Authorization"] = auth_header

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=msg.model_dump(), headers=headers or None)
            r.raise_for_status()
            response_data = r.json()

            duration_ms = (time.time() - start_time) * 1000
            log_response(logger, msg.id, agent, response_data.get("ok", True), duration_ms, endpoint=endpoint)

            return response_data
        except httpx.HTTPStatusError as exc:
            duration_ms = (time.time() - start_time) * 1000
            log_error(logger, msg.id, exc, agent=agent, endpoint=endpoint, status_code=exc.response.status_code, duration_ms=duration_ms)

            try:
                content = exc.response.json()
            except ValueError:
                content = {"detail": exc.response.text}
            return JSONResponse(status_code=exc.response.status_code, content=content)
        except httpx.HTTPError as exc:
            duration_ms = (time.time() - start_time) * 1000
            log_error(logger, msg.id, exc, agent=agent, endpoint=endpoint, duration_ms=duration_ms)
            raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/health")
def health():
    return {"ok": True, "ts": time.time(), "agents": list(AGENT_URLS.keys())}
