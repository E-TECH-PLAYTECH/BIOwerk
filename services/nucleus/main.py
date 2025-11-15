from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
import time, httpx

app = FastAPI(title="Nucleus")
setup_instrumentation(app)

AGENTS = {
    "osteon": "http://mesh:8080/osteon",
    "myocyte": "http://mesh:8080/myocyte",
    "synapse": "http://mesh:8080/synapse",
    "circadian": "http://mesh:8080/circadian",
}

@app.post("/plan", response_model=Reply)
def plan(msg: Msg):
    output = {"plan":[
        {"step_id":"s1","agent":"osteon","endpoint":"outline"},
        {"step_id":"s2","agent":"osteon","endpoint":"draft","depends_on":["s1"]},
        {"step_id":"s3","agent":"synapse","endpoint":"slide_make","depends_on":["s2"]}
    ]}
    return Reply(id=msg.id, ts=time.time(), agent="nucleus", ok=True, output=output, state_hash=state_hash(output))

@app.post("/route", response_model=Reply)
def route(msg: Msg):
    # Stubbed router
    output = {"routed": True}
    return Reply(id=msg.id, ts=time.time(), agent="nucleus", ok=True, output=output, state_hash=state_hash(output))

@app.post("/review", response_model=Reply)
def review(msg: Msg):
    output = {"criteria":["hash-stable","schema-valid"], "pass": True}
    return Reply(id=msg.id, ts=time.time(), agent="nucleus", ok=True, output=output, state_hash=state_hash(output))

@app.post("/finalize", response_model=Reply)
def finalize(msg: Msg):
    output = {"final":"ok"}
    return Reply(id=msg.id, ts=time.time(), agent="nucleus", ok=True, output=output, state_hash=state_hash(output))
