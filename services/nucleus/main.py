from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
from matrix.logging_config import setup_logging, log_request, log_response, log_error
from matrix.errors import create_error_response
import time, httpx

app = FastAPI(title="Nucleus")
setup_instrumentation(app)
logger = setup_logging("nucleus")

AGENTS = {
    "osteon": "http://mesh:8080/osteon",
    "myocyte": "http://mesh:8080/myocyte",
    "synapse": "http://mesh:8080/synapse",
    "circadian": "http://mesh:8080/circadian",
}

@app.post("/plan", response_model=Reply)
def plan(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "nucleus", "plan")

    try:
        output = {"plan":[
            {"step_id":"s1","agent":"osteon","endpoint":"outline"},
            {"step_id":"s2","agent":"osteon","endpoint":"draft","depends_on":["s1"]},
            {"step_id":"s3","agent":"synapse","endpoint":"slide_make","depends_on":["s2"]}
        ]}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "nucleus", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="nucleus", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "nucleus", e))

@app.post("/route", response_model=Reply)
def route(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "nucleus", "route")

    try:
        # Stubbed router
        output = {"routed": True}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "nucleus", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="nucleus", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "nucleus", e))

@app.post("/review", response_model=Reply)
def review(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "nucleus", "review")

    try:
        output = {"criteria":["hash-stable","schema-valid"], "pass": True}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "nucleus", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="nucleus", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "nucleus", e))

@app.post("/finalize", response_model=Reply)
def finalize(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "nucleus", "finalize")

    try:
        output = {"final":"ok"}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "nucleus", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="nucleus", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "nucleus", e))
