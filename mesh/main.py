from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request
import os, httpx, time
from matrix.models import Msg, Reply
from matrix.utils import state_hash

app = FastAPI(title="Mesh Gateway")

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
    data = await request.json()
    msg = Msg(**data)
    target_base = AGENT_URLS.get(agent)
    if not target_base:
        return {"error": f"unknown agent {agent}"}
    url = f"{target_base}/{endpoint}"
    headers = {}
    auth_header = request.headers.get("authorization")
    if auth_header:
        headers["Authorization"] = auth_header

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=msg.model_dump(), headers=headers or None)
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                content = exc.response.json()
            except ValueError:
                content = {"detail": exc.response.text}
            return JSONResponse(status_code=exc.response.status_code, content=content)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=msg.model_dump())
        r.raise_for_status()
        return r.json()

@app.get("/health")
def health():
    return {"ok": True, "ts": time.time(), "agents": list(AGENT_URLS.keys())}
