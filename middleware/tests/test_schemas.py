"""Schema-level tests for allowlisted commands and JSON aliases."""

from __future__ import annotations

import os

os.environ["PAIRING_TOKEN"] = "test-token"

import pytest
from pydantic import TypeAdapter, ValidationError

from schemas import ALLOWED_ACTIONS, Command, ConnectCommand, SetParCommand

ADAPTER = TypeAdapter(Command)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "action": "create_op",
            "parent_path": "/project1",
            "op_type": "textDAT",
            "name": "hello",
        },
        {
            "action": "set_par",
            "path": "/project1/hello",
            "par": "text",
            "value": "hi",
        },
        {
            "action": "set_par",
            "path": "/project1/hello",
            "par": "size",
            "value": 4,
        },
        {
            "action": "set_par",
            "path": "/project1/hello",
            "par": "gain",
            "value": 0.5,
        },
        {
            "action": "set_par",
            "path": "/project1/hello",
            "par": "on",
            "value": True,
        },
        {
            "action": "connect",
            "from": "/project1/out",
            "to_path": "/project1/in",
        },
        {
            "action": "connect",
            "from_path": "/project1/out",
            "to_path": "/project1/in",
            "input_index": 1,
        },
        {"action": "list_ops", "path": "/project1"},
        {"action": "delete_op", "path": "/project1/hello"},
    ],
)
def test_valid_command_passes_validation(payload: dict) -> None:
    cmd = ADAPTER.validate_python(payload)
    assert cmd.action in ALLOWED_ACTIONS


@pytest.mark.parametrize("action", ["write_script", "exec", "quit", "save"])
def test_off_allowlist_action_raises_validation_error(action: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ADAPTER.validate_python({"action": action, "path": "/project1"})
    assert action in str(exc_info.value)


def test_connect_serializes_from_path_as_from() -> None:
    cmd = ConnectCommand(action="connect", from_path="/a", to_path="/b")
    dumped = cmd.model_dump(by_alias=True)
    assert dumped["from"] == "/a"
    assert "from_path" not in dumped


def test_connect_accepts_json_from_key() -> None:
    cmd = ConnectCommand.model_validate(
        {"action": "connect", "from": "/src", "to_path": "/dst"}
    )
    assert cmd.from_path == "/src"


def test_set_par_rejects_non_scalar_value() -> None:
    with pytest.raises(ValidationError):
        SetParCommand.model_validate(
            {
                "action": "set_par",
                "path": "/p",
                "par": "text",
                "value": ["not", "a", "scalar"],
            }
        )


def test_optional_session_defaults_to_none() -> None:
    cmd = ADAPTER.validate_python(
        {"action": "list_ops", "path": "/project1"}
    )
    assert cmd.session is None
