from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.utils import state_hash
import time

app = FastAPI(title="Myocyte")

@app.post("/ingest_table", response_model=Reply)
def ingest_table(msg: Msg):
    output = {"tables": msg.input.get("tables", [])}
    return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))

@app.post("/formula_eval", response_model=Reply)
def formula_eval(msg: Msg):
    output = {"tables": msg.input.get("tables", []), "formulas": msg.input.get("formulas", []), "charts_spec":[]}
    return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))

@app.post("/model_forecast", response_model=Reply)
def model_forecast(msg: Msg):
    output = {"forecast":{"desc":"stub"}}
    return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))

@app.post("/export", response_model=Reply)
def export_(msg: Msg):
    output = {"artifact":{"kind":"myotab","meta":{"title":"untitled"},"body":{"tables":[],"formulas":[],"charts":[]}}}
    return Reply(id=msg.id, ts=time.time(), agent="myocyte", ok=True, output=output, state_hash=state_hash(output))
