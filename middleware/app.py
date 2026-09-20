"""TD agent middleware: WebSocket hub for TouchDesigner plus REST /cmd.

TD instances connect *out* to ``/ws`` and register with a pairing token.
Agents (and tests) call ``POST /cmd``; this process validates the action
against ALLOWED_ACTIONS, then forwards the JSON to the named TD session.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from config import Settings, load_settings
from schemas import ALLOWED_ACTIONS, Command, RegisterMessage, Reply

logger = logging.getLogger("td_middleware")

_settings: Settings | None = None
_audit: AuditLog | None = None


class TdSession:
    """In-memory record of one connected TouchDesigner WebSocket."""

    def __init__(self, websocket: WebSocket, session_name: str) -> None:
        self.websocket = websocket
        self.session_name = session_name
        self.connected_at: datetime = datetime.now(timezone.utc)
        self.last_command: str | None = None
        self.pending: asyncio.Future[dict[str, Any]] | None = None


class SessionManager:
    """Tracks connected TD sessions by human-readable name."""

    def __init__(self) -> None:
        self._sessions: dict[str, TdSession] = {}

    def get(self, name: str) -> TdSession | None:
        """Return the session named ``name``, or None if it is not connected."""
        return self._sessions.get(name)

    def list_sessions(self) -> list[TdSession]:
        """Return a snapshot of currently connected sessions."""
        return list(self._sessions.values())

    def connected_count(self) -> int:
        """Return how many TD instances are currently registered."""
        return len(self._sessions)

    def put(self, session: TdSession) -> TdSession | None:
        """Store ``session``, returning the previous occupant if replaced."""
        old = self._sessions.get(session.session_name)
        self._sessions[session.session_name] = session
        return old

    def remove_if_current(self, name: str, session: TdSession) -> bool:
        """Drop ``name`` only if ``session`` is still the stored connection."""
        current = self._sessions.get(name)
        if current is session:
            del self._sessions[name]
            return True
        return False

    def resolve(self, name: str | None) -> TdSession:
        """Pick the TD session that should receive a command.

        Raises:
            SessionLookupError: none connected, named session missing, or
                multiple connected and no name was given.
        """
        if name:
            session = self._sessions.get(name)
            if session is None:
                raise SessionLookupError(
                    503, f"session {name!r} is not connected"
                )
            return session
        count = len(self._sessions)
        if count == 0:
            raise SessionLookupError(503, "no TouchDesigner session is connected")
        if count > 1:
            raise SessionLookupError(
                409,
                "multiple sessions are connected; specify the session field",
            )
        return next(iter(self._sessions.values()))


class SessionLookupError(Exception):
    """Session routing failed; ``status_code`` is 409 or 503."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class AuditLog:
    """Append-only JSONL audit log. The file is created on first write."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._ready = False
        self._lock = threading.Lock()

    def write(self, record: dict[str, Any]) -> None:
        """Append one JSON object as a single line."""
        line = json.dumps(record, default=str)
        with self._lock:
            if not self._ready:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._ready = True
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


manager = SessionManager()


def get_settings() -> Settings:
    """Return cached settings, loading from the environment on first call.

    Tests may replace this via ``app.dependency_overrides`` or by setting
    ``PAIRING_TOKEN`` before importing this module.
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def get_audit() -> AuditLog:
    """Return the process-wide audit log, created lazily."""
    global _audit
    if _audit is None:
        _audit = AuditLog(get_settings().audit_log_path)
    return _audit


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )


def _error_body(message: str) -> dict[str, Any]:
    return Reply(ok=False, error=message, debug={}).model_dump(exclude_none=True)


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_error_body(message))


def _command_payload(command: Command) -> dict[str, Any]:
    """Serialize a validated command for the TD WebSocket (JSON key ``from``)."""
    return command.model_dump(mode="json", by_alias=True, exclude={"session"})


def _audit_cmd(
    command: Command,
    reply: dict[str, Any],
    latency_ms: float,
) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cmd": command.model_dump(mode="json", by_alias=True),
        "reply": reply,
        "latency_ms": round(latency_ms, 3),
    }
    try:
        get_audit().write(record)
    except OSError:
        logger.exception("failed to write audit log")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Load settings at startup so a missing production token fails fast."""
    _configure_logging()
    settings = get_settings()
    logger.setLevel(logging.DEBUG)
    logger.info(
        "middleware ready (bind later via uvicorn); timeout=%.1fs; allowlist=%s",
        settings.cmd_timeout_seconds,
        sorted(ALLOWED_ACTIONS),
    )
    logger.info(
        "[WS-DEBUG] websocket catch-all enabled: routes '/' and "
        "'/{full_path:path}' (includes /ws); verbose register logging on"
    )
    yield


app = FastAPI(
    title="TD Agent Middleware",
    description="Pairing-token WebSocket hub for TouchDesigner command execution.",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, bool]:
    """Render / load-balancer health check."""
    return {"ok": True}


@app.get("/sessions")
async def list_sessions() -> dict[str, list[dict[str, Any]]]:
    """List currently connected TouchDesigner sessions."""
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for session in manager.list_sessions():
        rows.append(
            {
                "session": session.session_name,
                "connected_at": session.connected_at.isoformat(),
                "last_command": session.last_command,
                "duration_seconds": (now - session.connected_at).total_seconds(),
            }
        )
    return {"sessions": rows}


@app.post("/cmd")
async def post_cmd(
    command: Command,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Validate an allowlisted command and route it to a connected TD session."""
    started = time.perf_counter()
    try:
        session = manager.resolve(command.session)
    except SessionLookupError as exc:
        body = _error_body(exc.message)
        _audit_cmd(command, body, (time.perf_counter() - started) * 1000)
        return JSONResponse(status_code=exc.status_code, content=body)

    if session.pending is not None and not session.pending.done():
        body = _error_body("a command is already in flight for this session")
        _audit_cmd(command, body, (time.perf_counter() - started) * 1000)
        return JSONResponse(status_code=409, content=body)

    loop = asyncio.get_running_loop()
    pending: asyncio.Future[dict[str, Any]] = loop.create_future()
    session.pending = pending
    session.last_command = command.action
    payload = _command_payload(command)

    try:
        await session.websocket.send_json(payload)
        reply = await asyncio.wait_for(
            asyncio.shield(pending),
            timeout=settings.cmd_timeout_seconds,
        )
    except TimeoutError:
        body = _error_body("timed out waiting for TouchDesigner reply")
        _audit_cmd(command, body, (time.perf_counter() - started) * 1000)
        return JSONResponse(status_code=504, content=body)
    except Exception as exc:
        logger.exception("failed to deliver command to session %s", session.session_name)
        body = _error_body(f"failed to deliver command: {exc}")
        _audit_cmd(command, body, (time.perf_counter() - started) * 1000)
        return JSONResponse(status_code=503, content=body)
    finally:
        if session.pending is pending:
            session.pending = None

    if not isinstance(reply, dict):
        reply = {
            "ok": False,
            "error": "TouchDesigner returned a non-object reply",
            "debug": {},
        }
    _audit_cmd(command, reply, (time.perf_counter() - started) * 1000)
    return JSONResponse(status_code=200, content=reply)


def _ws_requested_path(full_path: str) -> str:
    """Normalize a websocket path param to a slash-prefixed request path."""
    if not full_path:
        return "/"
    return "/" + full_path.lstrip("/")


def _ws_client_label(websocket: WebSocket) -> str:
    client = websocket.client
    if client is None:
        return "unknown"
    return f"{client.host}:{client.port}"


def _ws_header_summary(websocket: WebSocket) -> str:
    """Log a few handshake headers; never dump cookies or authorization."""
    interesting = (
        "host",
        "user-agent",
        "origin",
        "sec-websocket-protocol",
        "sec-websocket-version",
        "sec-websocket-extensions",
    )
    parts: list[str] = []
    for key in interesting:
        value = websocket.headers.get(key)
        if value:
            parts.append(f"{key}={value!r}")
    return ", ".join(parts) if parts else "(none of interest)"


def _token_match_summary(provided: str, expected: str) -> str:
    """Describe a token comparison without logging the secret itself."""
    suffix = provided[-2:] if len(provided) >= 2 else provided
    return (
        f"match={provided == expected} provided_len={len(provided)} "
        f"expected_len={len(expected)} provided_last2={suffix!r}"
    )


@app.websocket("/")
@app.websocket("/{full_path:path}")
async def websocket_endpoint(
    websocket: WebSocket,
    full_path: str = "",
    settings: Settings = Depends(get_settings),
) -> None:
    """Accept a TD client on any path. The first message must be a valid register."""
    requested_path = _ws_requested_path(full_path)
    logger.info(
        "[WS-DEBUG] incoming websocket path=%s url_path=%s client=%s headers=%s",
        requested_path,
        websocket.url.path,
        _ws_client_label(websocket),
        _ws_header_summary(websocket),
    )
    await websocket.accept()
    session: TdSession | None = None
    session_name = ""

    try:
        first = await websocket.receive_json()
    except WebSocketDisconnect:
        logger.info("[WS-DEBUG] register rejected: closed before first message")
        logger.info("websocket closed before register")
        return
    except Exception:
        logger.info("[WS-DEBUG] register rejected: first message was not JSON")
        logger.info("websocket first message was not JSON; closing")
        await websocket.close(code=1003)
        return

    try:
        register = RegisterMessage.model_validate(first)
    except ValidationError as exc:
        field_bits = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", ()))
            field_bits.append(f"{loc}:{err.get('type')}")
        logger.info(
            "[WS-DEBUG] register rejected: missing fields / invalid register "
            "shape (%s); first message was not a register",
            ", ".join(field_bits) or "unknown",
        )
        await websocket.send_json(
            _error_body("first message must be a register with token and session")
        )
        await websocket.close(code=1008)
        return

    token_summary = _token_match_summary(register.token, settings.pairing_token)
    logger.info(
        "[WS-DEBUG] register attempt session=%r %s",
        register.session,
        token_summary,
    )

    # Token check happens before any other message is accepted or stored.
    if register.token != settings.pairing_token:
        logger.info(
            "[WS-DEBUG] register rejected: wrong token session=%r %s",
            register.session,
            token_summary,
        )
        logger.warning("rejected register for session %s: invalid token", register.session)
        await websocket.send_json(_error_body("invalid pairing token"))
        await websocket.close(code=1008)
        return

    session_name = register.session.strip()
    if not session_name:
        logger.info("[WS-DEBUG] register rejected: blank session name")
        await websocket.send_json(_error_body("session name is required"))
        await websocket.close(code=1008)
        return

    session = TdSession(websocket, session_name)
    previous = manager.put(session)
    if previous is not None:
        logger.info("session %s reconnected; replacing previous socket", session_name)
        if previous.pending is not None and not previous.pending.done():
            previous.pending.set_result(
                {"ok": False, "error": "session replaced by a new connection", "debug": {}}
            )
        try:
            await previous.websocket.close()
        except Exception:
            logger.debug("error closing replaced websocket for %s", session_name, exc_info=True)
    else:
        logger.info("registered session %s", session_name)
    logger.info("[WS-DEBUG] register success: session %r stored", session_name)

    await websocket.send_json({"ok": True, "session_id": session_name})

    try:
        await _receive_replies(session)
    except WebSocketDisconnect:
        logger.info("session %s disconnected", session_name)
    except Exception:
        logger.exception("session %s websocket error", session_name)
    finally:
        if session.pending is not None and not session.pending.done():
            session.pending.set_result(
                {"ok": False, "error": "TouchDesigner disconnected", "debug": {}}
            )
        if manager.remove_if_current(session_name, session):
            logger.info("removed session %s", session_name)


async def _receive_replies(session: TdSession) -> None:
    """Read TD replies and complete the in-flight Future, if any."""
    while True:
        data = await session.websocket.receive_json()
        pending = session.pending
        if pending is not None and not pending.done():
            if not isinstance(data, dict):
                pending.set_result(
                    {
                        "ok": False,
                        "error": "TouchDesigner returned a non-object reply",
                        "debug": {},
                    }
                )
            else:
                pending.set_result(data)
        else:
            logger.warning(
                "unexpected message from session %s (no in-flight command)",
                session.session_name,
            )


if __name__ == "__main__":
    import uvicorn

    _configure_logging()
    _main_settings = load_settings()
    uvicorn.run(
        app,
        host=_main_settings.bind_host,
        port=_main_settings.port,
    )
