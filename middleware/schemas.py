"""Pydantic v2 command and reply models for the TD agent middleware.

ALLOWED_ACTIONS is the service-side allowlist — the single source of truth
for which actions this process will accept. FastAPI validates incoming
POST /cmd bodies against this set (off-allowlist → ValidationError → 422)
before anything is forwarded to TouchDesigner.

Adding a new action later (e.g. write_script):
  1. Add one string to ALLOWED_ACTIONS below.
  2. Add one string to ALLOWED_ACTIONS in plugin/td_agent_callbacks.py.
  3. Add a small command model and register it in the Command union.
  4. Add a handle_<action> function in the plugin callbacks.
"""

from __future__ import annotations

from typing import Annotated, Any, Final, Literal, Union

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# THE service-side allowlist. Referenced by validation (see _ensure_allowed_action)
# and by comments/docs. Do not scatter action-name string literals elsewhere in
# the service — add the string here, then add a model class to the Command union.
ALLOWED_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "create_op",
        "set_par",
        "connect",
        "list_ops",
        "delete_op",
        # "write_script",  # later phase — do not implement now
    }
)


def _ensure_allowed_action(data: Any) -> Any:
    """Reject actions outside ALLOWED_ACTIONS before union dispatch.

    Unknown actions never reach TouchDesigner. A missing action is left to
    the discriminated union so the 422 details stay field-accurate.
    """
    if isinstance(data, dict):
        action = data.get("action")
        if action is not None and action not in ALLOWED_ACTIONS:
            raise ValueError(
                f"action {action!r} is not allowed; "
                f"permitted actions: {sorted(ALLOWED_ACTIONS)}"
            )
    return data


class CommandBase(BaseModel):
    """Shared fields for every allowlisted command."""

    model_config = ConfigDict(populate_by_name=True)

    session: str | None = None
    """Optional TD session name for POST /cmd routing."""


class CreateOpCommand(CommandBase):
    """Create an operator under ``parent_path``."""

    action: Literal["create_op"]
    parent_path: str
    op_type: str
    name: str


class SetParCommand(CommandBase):
    """Set a parameter value on an existing operator."""

    action: Literal["set_par"]
    path: str
    par: str
    value: str | int | float | bool


class ConnectCommand(CommandBase):
    """Wire ``from_path`` into ``to_path`` at ``input_index``.

    The Python field is ``from_path``; the JSON key is ``from``.
    """

    action: Literal["connect"]
    from_path: str = Field(alias="from", serialization_alias="from")
    to_path: str
    input_index: int = 0


class ListOpsCommand(CommandBase):
    """List child operators of ``path``."""

    action: Literal["list_ops"]
    path: str


class DeleteOpCommand(CommandBase):
    """Destroy the operator at ``path``."""

    action: Literal["delete_op"]
    path: str


Command = Annotated[
    Union[
        CreateOpCommand,
        SetParCommand,
        ConnectCommand,
        ListOpsCommand,
        DeleteOpCommand,
    ],
    BeforeValidator(_ensure_allowed_action),
    Field(discriminator="action"),
]


class Reply(BaseModel):
    """Contract reply returned by TouchDesigner and by this service on errors."""

    ok: bool
    result: str | None = None
    error: str | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class RegisterMessage(BaseModel):
    """First WebSocket message a TD client must send after connecting."""

    action: Literal["register"]
    token: str
    session: str
