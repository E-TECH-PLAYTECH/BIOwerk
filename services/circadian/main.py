from fastapi import FastAPI
from matrix.models import Msg, Reply
from matrix.utils import state_hash
import time

app = FastAPI(title="Circadian")

@app.post("/plan_timeline", response_model=Reply)
def plan_timeline(msg: Msg):
    goals = msg.input.get("goals", [])
    output = {"timeline":[{"milestone":"M1","desc":"Scaffold running"}], "assignments":[], "risks":[], "next_actions":[{"do":"run docker compose"}]}
    return Reply(id=msg.id, ts=time.time(), agent="circadian", ok=True, output=output, state_hash=state_hash(output))

@app.post("/assign", response_model=Reply)
def assign(msg: Msg):
    output = {"assignments": msg.input.get("assignments", [])}
    return Reply(id=msg.id, ts=time.time(), agent="circadian", ok=True, output=output, state_hash=state_hash(output))

@app.post("/track", response_model=Reply)
def track(msg: Msg):
    output = {"status":"green"}
    return Reply(id=msg.id, ts=time.time(), agent="circadian", ok=True, output=output, state_hash=state_hash(output))

@app.post("/remind", response_model=Reply)
def remind(msg: Msg):
    output = {"reminders":["stub"]}
    return Reply(id=msg.id, ts=time.time(), agent="circadian", ok=True, output=output, state_hash=state_hash(output))
