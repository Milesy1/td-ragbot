"""
td_agent — agent loop for building TouchDesigner networks through the governed
td-middleware chokepoint (github.com/Milesy1/td-ragbot).

Trust model: the LLM proposes, the middleware disposes. The loop can only emit
the six allowlisted actions; every request is auth-gated, audit-logged, and
every reply is structured. Failure taxonomy distinguishes "never arrived"
(transport) from "rejected" (auth/contract) from "TD said no" (executor) —
only contract+executor are LLM-diagnosable; auth/transport/parse abort.

Groq note: gpt-oss models are natively tool-trained — do NOT use
response_format=json_object with them (API rejects tool calls in that mode).
GroqLLM below speaks native function calling and adapts calls back into the
loop's JSON protocol, so the loop itself is provider-agnostic.

Usage (live, with Groq):
    pip install requests groq
    $env:PAIRING_TOKEN = "<64-hex>"
    $env:GROQ_API_KEY  = "<key>"
    python -c "from td_agent import AgentLoop, GroqLLM, MiddlewareClient, Transcript; \
        AgentLoop(MiddlewareClient(), GroqLLM(), Transcript('run1.jsonl')).run('create a base called fx with a \
        circleTOP and levelTOP inside, level opacity 0.5, then verify')"

Usage (scripted acceptance test, no LLM):
    $env:PAIRING_TOKEN = "<64-hex>"
    python test_fx_build.py
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Callable, Protocol

import requests

# --------------------------------------------------------------------------- config

BASE_URL = os.environ.get("TD_MIDDLEWARE_URL", "https://td-middleware.onrender.com").rstrip("/")
SESSION = os.environ.get("TD_SESSION", "studio-pc")
PAIRING_TOKEN = os.environ.get("PAIRING_TOKEN")  # fail fast at client build if missing

# --------------------------------------------------------------------------- replies

class Failure(str, Enum):
    OK = "ok"                    # ok: true, op_errors empty
    TRANSPORT = "transport"      # request never reached middleware (DNS/timeout/conn)
    AUTH = "auth"                # 401 — not LLM-fixable; abort
    CONTRACT = "contract"        # 422 — schema rejection; LLM can adapt args
    EXECUTOR = "executor"        # reached TD, ok:false or op_errors; LLM can adapt
    PARSE = "parse"              # non-JSON reply; middleware bug, abort

RETRYABLE = {Failure.CONTRACT, Failure.EXECUTOR}   # LLM-diagnosable
ABORT = {Failure.AUTH, Failure.TRANSPORT, Failure.PARSE}

@dataclass
class Reply:
    action: str
    ok: bool | None
    result: Any
    op_errors: list
    debug: dict
    failure: Failure
    http_status: int | None
    latency_ms: float

    @property
    def path(self) -> str | None:
        """Actual path of a created op — NEVER assume it matches the request
        (create_op auto-increments on collision: fx -> fx1). Always route via here."""
        return self.result if isinstance(self.result, str) else None

    def describe(self) -> str:
        if self.failure is Failure.OK:
            return f"ok: true, result: {self.result!r}"
        return (f"failure={self.failure.value} http={self.http_status} "
                f"op_errors={self.op_errors!r} result={self.result!r}")

# --------------------------------------------------------------------------- client

class MiddlewareClient:
    def __init__(self, base_url: str = BASE_URL, token: str | None = PAIRING_TOKEN,
                 session: str = SESSION, timeout: float = 30.0):
        if not token:
            raise RuntimeError("PAIRING_TOKEN not set — refusing to build a client")
        self.base, self.token, self.session, self.timeout = base_url, token, session, timeout

    def cmd(self, action: str, **fields) -> Reply:
        body = {"action": action, "session": self.session, **fields}
        t0 = time.perf_counter()
        try:
            r = requests.post(f"{self.base}/cmd", json=body,
                              headers={"X-Pairing-Token": self.token},
                              timeout=self.timeout)
        except requests.RequestException:
            return Reply(action, None, None, [], {}, Failure.TRANSPORT, None,
                         (time.perf_counter() - t0) * 1000)
        ms = (time.perf_counter() - t0) * 1000
        try:
            data = r.json()
        except ValueError:
            return Reply(action, None, None, [], {}, Failure.PARSE, r.status_code, ms)
        ok = data.get("ok")
        errs = data.get("op_errors") or []
        if r.status_code == 401:
            fail = Failure.AUTH
        elif r.status_code == 422:
            fail = Failure.CONTRACT
        else:
            fail = Failure.OK if ok and not errs else Failure.EXECUTOR
        return Reply(action, ok, data.get("result"), errs,
                     data.get("debug") or {}, fail, r.status_code, ms)

# --------------------------------------------------------------------------- tools

def tool_specs() -> list[dict]:
    """Loop-level tool catalog. The six td_* tools mirror the middleware
    contract (middleware/README.md Command API); td_finish is loop-local and
    never reaches the middleware. Regenerate from the Pydantic schema when
    the executor generator lands."""
    return [
        {"name": "td_create_op",
         "description": "Create an operator. parent_path must be an existing container (e.g. /project1). "
                        "op_type is the TouchDesigner operator class, case-sensitive (baseCOMP, circleTOP, levelTOP).",
         "args": {"parent_path": "string", "op_type": "string", "name": "string"},
         "returns": "actual path of created op (auto-increments on collision — use it)"},
        {"name": "td_set_par",
         "description": "Set a parameter on an operator.",
         "args": {"path": "string", "par": "string", "value": "number|string"}},
        {"name": "td_connect",
         "description": "Connect two operators (output of 'from' into input of 'to_path').",
         "args": {"from": "string", "to_path": "string"}},
        {"name": "td_list_ops",
         "description": "List operators inside a container. path is REQUIRED (e.g. /project1).",
         "args": {"path": "string"}},
        {"name": "td_delete_op",
         "description": "Delete an operator and its children.",
         "args": {"path": "string"}},
        {"name": "td_get_op_info",
         "description": "Read-only introspection: name, optype, all par values (Token redacted), cook_ms, inputs, outputs.",
         "args": {"path": "string"}},
        {"name": "td_finish",
         "description": "Call when the goal is fully verified. Never reaches TouchDesigner.",
         "args": {"summary": "string"}},
    ]

_TOOL_TO_ACTION = {
    "td_create_op": "create_op", "td_set_par": "set_par", "td_connect": "connect",
    "td_list_ops": "list_ops", "td_delete_op": "delete_op", "td_get_op_info": "get_op_info",
}
_LOOP_LOCAL = {"td_finish"}

def call_tool(client: MiddlewareClient, name: str, args: dict) -> Reply:
    if name in _LOOP_LOCAL:
        raise KeyError(f"{name} is loop-local — the LLM adapter handles it, never call it here")
    action = _TOOL_TO_ACTION.get(name)
    if action is None:
        raise KeyError(f"unknown tool {name!r} — allowlist violation")
    return client.cmd(action, **args)

# --------------------------------------------------------------------------- verify

def verify_par(client: MiddlewareClient, path: str, par: str, expected: float,
               tol: float = 1e-3) -> tuple[bool, str]:
    """Read-back verification — the entire point of get_op_info."""
    r = client.cmd("get_op_info", path=path)
    if r.failure is not Failure.OK or not isinstance(r.result, dict):
        return False, f"get_op_info failed: {r.describe()}"
    actual = r.result.get("pars", {}).get(par)
    try:
        if abs(float(actual) - expected) <= tol:
            return True, f"{path}.{par} == {actual} (expected {expected})"
        return False, f"{path}.{par} == {actual}, expected {expected}"
    except (TypeError, ValueError):
        return False, f"{path}.{par} unreadable: {actual!r}"

# --------------------------------------------------------------------------- llm

class LLM(Protocol):
    def complete(self, messages: list[dict]) -> str: ...

def _json_schema_props(args: dict) -> dict:
    props = {}
    for k, v in args.items():
        props[k] = {"type": "string"} if v == "string" else {}
    return props

class GroqLLM:
    """Native function calling on Groq (gpt-oss / llama-4 / qwen3 all support it).
    Adapts tool calls back into the loop's JSON protocol — the loop itself
    never knows the difference. Do NOT add response_format here."""
    def __init__(self, model: str = "openai/gpt-oss-20b"):
        from groq import Groq
        self.client = Groq(api_key=os.environ["GROQ_API_KEY"])
        self.model = model

    def _tools(self) -> list[dict]:
        return [{
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", t["name"]),
                "parameters": {
                    "type": "object",
                    "properties": _json_schema_props(t["args"]),
                    "required": list(t["args"].keys()),
                },
            },
        } for t in tool_specs()]

    def complete(self, messages: list[dict]) -> str:
        r = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0,
            tools=self._tools(), tool_choice="auto")
        msg = r.choices[0].message
        if msg.tool_calls:
            call = msg.tool_calls[0]
            args = json.loads(call.function.arguments or "{}")
            if call.function.name == "td_finish":
                return json.dumps({"done": True, "summary": args.get("summary", "")})
            return json.dumps({"tool": call.function.name, "args": args})
        return msg.content or "{}"

class ScriptedLLM:
    """Deterministic planner for acceptance tests: next action is a function of
    the transcript so far. Proves loop mechanics without burning tokens."""
    def __init__(self, planner: Callable[[list["Step"]], dict]):
        self.planner, self.calls = planner, 0
        self.steps: list["Step"] = []

    def complete(self, messages: list[dict]) -> str:
        self.calls += 1
        return json.dumps(self.planner(self.steps))

# --------------------------------------------------------------------------- loop

SYSTEM_PROMPT = """You control TouchDesigner through a governed middleware. You have exactly these tools:
%s

Rules:
1. NEVER invent an op path. After td_create_op, continue from the path in its reply's result — it may differ from the name you asked for (auto-increment on collision).
2. After every td_set_par, verify with td_get_op_info before moving on.
3. If a tool reply reports failure, diagnose from the error and change your next action accordingly — never repeat an identical failed call.
4. When the goal is fully verified, call td_finish with a one-line summary. Nothing else ends the run.
5. Do not delete what you built unless asked.""" % (
    "\n".join(f"- {t['name']}({json.dumps(t['args'])}): {t.get('description', '')} {t.get('returns', '')}"
              for t in tool_specs()))

@dataclass
class Step:
    index: int
    tool: str
    args: dict
    reply: Reply | None
    note: str = ""

class Transcript:
    """JSONL audit trail — doubles as eval seed data (one line per step)."""
    def __init__(self, path: str):
        self.f = open(path, "a", encoding="utf-8")

    def record(self, step: Step) -> None:
        self.f.write(json.dumps({
            "ts": time.time(), "index": step.index, "tool": step.tool,
            "args": step.args, "note": step.note,
            "reply": None if step.reply is None else asdict(step.reply),
        }) + "\n")
        self.f.flush()

    def close(self) -> None:
        self.f.close()

class AgentLoop:
    def __init__(self, client: MiddlewareClient, llm: LLM,
                 transcript: Transcript | None = None,
                 max_steps: int = 24, max_tool_retries: int = 2):
        self.client, self.llm = client, llm
        self.transcript, self.max_steps, self.max_tool_retries = transcript, max_steps, max_tool_retries
        self.steps: list[Step] = []

    def run(self, goal: str) -> list[Step]:
        if isinstance(self.llm, ScriptedLLM):
            self.llm.steps = self.steps
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": goal}]
        retries = 0
        for i in range(self.max_steps):
            raw = self.llm.complete(messages)
            try:
                intent = json.loads(raw)
            except ValueError:
                messages.append({"role": "user", "content":
                    "Your last reply was not valid JSON. Reply with exactly one JSON object."})
                continue
            if intent.get("done"):
                self.steps.append(Step(i, "done", {}, None, intent.get("summary", "")))
                return self.steps
            step = Step(i, intent.get("tool", ""), intent.get("args", {}), None)
            try:
                step.reply = call_tool(self.client, step.tool, step.args)
            except KeyError as e:
                messages.append({"role": "user", "content": f"{e} — pick a tool from the list."})
                continue
            if self.transcript:
                self.transcript.record(step)
            self.steps.append(step)
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": step.reply.describe()})
            if step.reply.failure in ABORT:
                step.note = "abort — not LLM-diagnosable"
                return self.steps
            retries = retries + 1 if step.reply.failure in RETRYABLE else 0
            if retries > self.max_tool_retries:
                step.note = "retry budget exhausted"
                return self.steps
        return self.steps

    def ok(self) -> bool:
        return bool(self.steps) and self.steps[-1].tool == "done"
