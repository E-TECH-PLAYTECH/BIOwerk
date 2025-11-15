from fastapi import FastAPI, HTTPException
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
from matrix.logging_config import setup_logging, log_request, log_response, log_error
from matrix.errors import InvalidInputError, create_error_response
import time

app = FastAPI(title="Osteon")
setup_instrumentation(app)
logger = setup_logging("osteon")

@app.post("/draft", response_model=Reply)
def draft(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "draft")

    try:
        inp = msg.input or {}
        sections = [{"id":"s1","title":"Introduction","text":f"Goal: {inp.get('goal','(none)')}"}]
        output = {"sections": sections, "toc": [s["title"] for s in sections], "citations":[]}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))

@app.post("/outline", response_model=Reply)
def outline(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "outline")

    try:
        output = {"outline":["Intro","Body","Conclusion"]}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))

@app.post("/edit", response_model=Reply)
def edit(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "edit")

    try:
        output = {"diff":"noop"}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))

@app.post("/summarize", response_model=Reply)
def summarize(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "summarize")

    try:
        output = {"summary":"...summary..."}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))

@app.post("/export", response_model=Reply)
def export_(msg: Msg):
    start_time = time.time()
    log_request(logger, msg.id, "osteon", "export")

    try:
        output = {"artifact":{"kind":"osteon","meta":{"title":"untitled"},"body":{"sections":[]}}}

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, "osteon", True, duration_ms)

        return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, e, duration_ms=duration_ms)
        return Reply(**create_error_response(msg.id, "osteon", e))
