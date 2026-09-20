# TD Agent Middleware

Versioned contract between this service, TouchDesigner, and any agent that
calls `POST /cmd`.

## Contract

Actions (allowlist — enforced in **both** this service and the TD callbacks).
`ALLOWED_ACTIONS` in `schemas.py` and `ALLOWED_ACTIONS` in
`plugin/td_agent_callbacks.py` are the single source of truth per side.

| Action | Fields |
|---|---|
| `create_op` | `parent_path`, `op_type`, `name` |
| `set_par` | `path`, `par`, `value` (str / int / float / bool) |
| `connect` | `from` (JSON; Python `from_path`), `to_path`, `input_index` (default 0) |
| `list_ops` | `path` |
| `delete_op` | `path` |

Every reply is JSON:

```json
{"ok": true, "result": "...", "error": "...", "debug": {}}
```

`ok` is always present. `result` and `error` are optional. `debug` is always
present and contains whatever TouchDesigner returns:

- `op_errors` (list, optional)
- `cook_ms` (number, optional)
- `network_errors` (list, optional, capped at 10)

---

## 1. What this is

TouchDesigner connects **out** over a WebSocket to this service (`/ws`) and
registers with a pairing token plus a human-readable session name.

Agents (Claude, Cursor, a script, a CI job) call **REST**: `POST /cmd` with an
allowlisted action. The service validates the body (off-allowlist → 422) and
forwards the JSON to the named TD session. TD executes it locally and replies
over the same socket.

There is no database. Sessions live in memory. The audit log is a JSONL file.
The pairing token is the entire auth model.

---

## 2. For TouchDesigner users

1. Add a **WebSocket DAT**. Set it to **Client** mode.
2. Add two custom parameters on that DAT:
   - `Token` (string) — same value as `PAIRING_TOKEN` on the service
   - `Session` (string) — a name you will recognize, e.g. `studio`
3. Paste the contents of `plugin/td_agent_callbacks.py` into the DAT's
   **callbacks** DAT.
4. Set the WebSocket URL:
   - Local: `ws://localhost:8000/ws` (or `ws://localhost:<PORT>/ws`)
   - Render: `wss://<service>.onrender.com/ws`

The callbacks send `{"action":"register","token":...,"session":...}` on
connect (`onConnect` = onOpen) and dispatch commands on
`onReceiveText` (= onMessage). They never call `exec`, `save`, or `quit`.

Confirm the login with `GET /sessions` — your session name, connect time, and
duration should appear.

---

## 3. Local run

From the `middleware/` directory:

```powershell
copy .env.example .env
# Set PAIRING_TOKEN to a long random string. Do not commit .env.

pip install -r requirements.txt

# PowerShell
$env:PAIRING_TOKEN = "your-dev-token"
$env:BIND_HOST = "127.0.0.1"
$env:PORT = "8000"
uvicorn app:app --host $env:BIND_HOST --port $env:PORT
```

Or: `python app.py` (reads `BIND_HOST` and `PORT` from the environment).

The default audit log path is `./audit.jsonl` (relative to the process
working directory). Override with `AUDIT_LOG_PATH`.

### Tests

Import style matches uvicorn (`from app import app`, `from schemas import ...`).

From this directory:

```powershell
pytest tests -v
```

From the repo root (`conftest.py` puts `middleware/` on `sys.path`):

```powershell
python -m pytest middleware/tests -v
```

Set `PAIRING_TOKEN=test-token` (the test modules do this before importing
the app). `AUDIT_LOG_PATH` is pointed at a temp file by `tests/conftest.py`.

---

## 4. Render deploy

Create a **Web Service** whose root is this `middleware/` directory (or set
the start command so it runs from here).

- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Env vars:
  - `PAIRING_TOKEN` (required — production refuses to boot without it)
  - `BIND_HOST=0.0.0.0`
  - `PORT` (Render provides this)
  - `AUDIT_LOG_PATH` optional; default `./audit.jsonl`
- Health check: `GET /health`
- Instance: keep it **always-on**. Sessions are in memory; a spin-down drops
  every TD connection.
- TLS is at Render's proxy. TouchDesigner uses `wss://<service>.onrender.com/ws`.

Production is detected when `RENDER` is set (Render sets this) or when
`ENVIRONMENT` / `APP_ENV` is `production`. A missing or empty
`PAIRING_TOKEN` then raises at startup.

---

## 5. API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | `{"ok": true}` — 200 |
| `GET` | `/sessions` | Connected TDs: session name, `connected_at` (ISO 8601), `last_command`, `duration_seconds` |
| `POST` | `/cmd` | Body is a `Command`. 200 returns the TD reply as-is. |
| `WS` | `/ws` | TD connects out and registers. |

### WebSocket register

First message from a client **must** be:

```json
{"action": "register", "token": "<PAIRING_TOKEN>", "session": "<name>"}
```

The token is checked before any other message is accepted. A bad token
closes the socket (nothing is stored). Success stores the connection by
session name and replies `{"ok": true, "session_id": "<name>"}`. A reconnect
with the same name replaces the old socket. Disconnect is normal: the
session is removed.

### `POST /cmd` status codes

- `200` — TD reply, returned as-is
- `422` — body failed validation (including off-allowlist actions)
- `409` — multiple sessions connected and no `session` field, or a command
  is already in flight for that session
- `503` — no session connected, or the named session is not connected
- `504` — TD did not reply within `CMD_TIMEOUT_SECONDS` (default 10)

If `session` is omitted and exactly one TD is connected, that session is used.

---

## 6. Audit log

JSONL, one line per `/cmd` call (including 503 / 409 / 504):

```json
{"ts": "...", "cmd": {...}, "reply": {...}, "latency_ms": 12.3}
```

The file is created lazily (mkdirs + open on first write). Default path:
`./audit.jsonl` (override with `AUDIT_LOG_PATH`).

---

## 7. Roadmap

Not implemented in this phase:

- `write_script` (and any other action beyond the five above)
- Approval gates before destructive commands
- Hosted token management (pairing token stays an env var)

---

## 8. Adding an action

A new action is a **one-line allowlist change in exactly two places**, plus
the handler/model:

1. One string in `middleware/schemas.py` → `ALLOWED_ACTIONS`
2. One string in `plugin/td_agent_callbacks.py` → `ALLOWED_ACTIONS`
3. A small Pydantic model, registered in the `Command` discriminated union
4. A `handle_<action>` function in the plugin callbacks

Those two `ALLOWED_ACTIONS` constants are the single source of truth per
side. Do not scatter action-name string literals in validation or dispatch.
