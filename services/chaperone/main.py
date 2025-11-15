from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
import time

app = FastAPI(title="Chaperone")
setup_instrumentation(app)

@app.post("/import_artifact", response_model=Reply)
def import_artifact(msg: Msg):
    # Map external formats to native JSON containers
    output = {"artifact":{"kind":"osteon","meta":{"title":"imported"},"body":{"sections":[{"id":"s1","title":"Imported","text":"..."}]}}}
    return Reply(id=msg.id, ts=time.time(), agent="chaperone", ok=True, output=output, state_hash=state_hash(output))

@app.post("/export_artifact", response_model=Reply)
def export_artifact(msg: Msg):
    # Map native to external formats (docx/xlsx/pptx/pdf) - stub
    output = {"export":{"format": msg.input.get("format","pdf"), "bytes_ref":"stub"}}
    return Reply(id=msg.id, ts=time.time(), agent="chaperone", ok=True, output=output, state_hash=state_hash(output))
