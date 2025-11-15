from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.utils import state_hash
import time

app = FastAPI(title="Osteon")

@app.post("/draft", response_model=Reply)
def draft(msg: Msg):
    inp = msg.input or {}
    sections = [{"id":"s1","title":"Introduction","text":f"Goal: {inp.get('goal','(none)')}"}]
    output = {"sections": sections, "toc": [s["title"] for s in sections], "citations":[]}
    return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))

@app.post("/outline", response_model=Reply)
def outline(msg: Msg):
    output = {"outline":["Intro","Body","Conclusion"]}
    return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))

@app.post("/edit", response_model=Reply)
def edit(msg: Msg):
    output = {"diff":"noop"}
    return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))

@app.post("/summarize", response_model=Reply)
def summarize(msg: Msg):
    output = {"summary":"...summary..."}
    return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))

@app.post("/export", response_model=Reply)
def export_(msg: Msg):
    output = {"artifact":{"kind":"osteon","meta":{"title":"untitled"},"body":{"sections":[]}}}
    return Reply(id=msg.id, ts=time.time(), agent="osteon", ok=True, output=output, state_hash=state_hash(output))
