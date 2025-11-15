from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import time, uuid

def new_id() -> str:
    return str(uuid.uuid4())

def now() -> float:
    return time.time()

class Msg(BaseModel):
    id: str = Field(default_factory=new_id)
    ts: float = Field(default_factory=now)
    origin: str
    target: str
    intent: str
    input: Dict[str, Any] = {}

class Reply(BaseModel):
    id: str
    ts: float
    agent: str
    ok: bool
    output: Dict[str, Any]
    state_hash: str
