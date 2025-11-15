from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
import time

app = FastAPI(title="Synapse")
setup_instrumentation(app)

@app.post("/storyboard", response_model=Reply)
def storyboard(msg: Msg):
    output = {"storyboard": msg.input.get("storyboard", [{"title":"Slide 1"}])}
    return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))

@app.post("/slide_make", response_model=Reply)
def slide_make(msg: Msg):
    output = {"slides":[{"id":"slide-1","title":"Title"}], "layout_graph":{}, "speaker_notes":[]}
    return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))

@app.post("/visualize", response_model=Reply)
def visualize(msg: Msg):
    output = {"viz":{"type":"bar","data":[1,2,3]}}
    return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))

@app.post("/export", response_model=Reply)
def export_(msg: Msg):
    output = {"artifact":{"kind":"synslide","meta":{"title":"untitled"},"body":{"slides":[],"layout_graph":{},"notes":[]}}}
    return Reply(id=msg.id, ts=time.time(), agent="synapse", ok=True, output=output, state_hash=state_hash(output))
