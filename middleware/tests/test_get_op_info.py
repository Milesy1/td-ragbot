"""Schema, HTTP, and mocked-executor tests for get_op_info."""

from __future__ import annotations

import os

os.environ["PAIRING_TOKEN"] = "test-token"

from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app import app
from schemas import ALLOWED_ACTIONS, Command
from td_executor.get_op_info import handle_get_op_info

ADAPTER = TypeAdapter(Command)

GET_OP_INFO_PAYLOAD = {
    "action": "get_op_info",
    "path": "/project1/fx/level1",
}


class FakePar:
    def __init__(self, name, value=None, error=None):
        self.name = name
        self._value = value
        self._error = error

    def eval(self):
        if self._error is not None:
            raise self._error
        return self._value


class FakeOp:
    def __init__(
        self,
        name="level1",
        optype="levelTOP",
        pars=None,
        cook_ms=0.12,
        inputs=None,
        outputs=None,
        children=None,
    ):
        self.name = name
        self.type = optype
        self.cookTime = cook_ms
        self.inputs = inputs if inputs is not None else []
        self.outputs = outputs if outputs is not None else []
        self.children = children if children is not None else []
        self._pars = pars if pars is not None else []

    def pars(self):
        return self._pars


def test_get_op_info_existing_op() -> None:
    cmd = ADAPTER.validate_python(GET_OP_INFO_PAYLOAD)
    assert cmd.action == "get_op_info"
    assert cmd.action in ALLOWED_ACTIONS
    assert cmd.path == "/project1/fx/level1"

    client = TestClient(app)
    response = client.post("/cmd", json=GET_OP_INFO_PAYLOAD)
    assert response.status_code == 503
    assert response.json()["ok"] is False

    target = FakeOp(
        pars=[FakePar("opacity", 1.0), FakePar("invert", 0)],
        inputs=[FakeOp(name="moviein1")],
        outputs=[FakeOp(name="out1")],
    )

    def op_lookup(path):
        if path == GET_OP_INFO_PAYLOAD["path"]:
            return target
        return None

    reply = handle_get_op_info(dict(GET_OP_INFO_PAYLOAD), op_lookup=op_lookup)
    assert reply["ok"] is True
    assert reply["op_errors"] == []
    assert reply["result"]["optype"] == "levelTOP"
    assert reply["result"]["name"] == "level1"
    assert isinstance(reply["result"]["pars"], dict)
    assert reply["result"]["pars"]["opacity"] == 1.0
    assert reply["result"]["cook_ms"] == 0.12
    assert reply["result"]["inputs"] == ["moviein1"]
    assert reply["result"]["outputs"] == ["out1"]
    assert reply["result"]["children"] == 0
    assert reply["debug"] == {}


def test_get_op_info_missing_path() -> None:
    reply = handle_get_op_info(
        {"action": "get_op_info", "path": "/project1/missing"},
        op_lookup=lambda path: None,
    )
    assert reply["ok"] is False
    assert reply["result"] is None
    assert any("op not found" in err for err in reply["op_errors"])
    assert "/project1/missing" in reply["op_errors"][0]


def test_get_op_info_unevaluable_par() -> None:
    target = FakeOp(
        pars=[
            FakePar("opacity", 1.0),
            FakePar("broken", error=RuntimeError("no cook")),
        ]
    )
    reply = handle_get_op_info(
        dict(GET_OP_INFO_PAYLOAD),
        op_lookup=lambda path: target,
    )
    assert reply["ok"] is True
    pars = reply["result"]["pars"]
    assert pars["opacity"] == 1.0
    assert pars["broken"].startswith("<unevaluable: ")
    assert "no cook" in pars["broken"]
