# TouchDesigner WebSocket DAT callbacks — paste this entire file into the
# callbacks DAT of a WebSocket DAT.
#
# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
# 1. Add a WebSocket DAT. Set it to Client mode.
# 2. URL:
#      Local:  ws://localhost:8000/ws   (or ws://localhost:<PORT>/ws)
#      Render: wss://<service>.onrender.com/ws
# 3. Add two custom parameters on the WebSocket DAT:
#      Token   (string)  — same value as PAIRING_TOKEN on the service
#      Session (string)  — human-readable name, e.g. "studio"
#    Accessed as me.par.Token / me.par.Session, or webSocketDAT.par.Token
#    / webSocketDAT.par.Session.
#
# Callback mapping (TD names → the names used in this file):
#   onConnect      = onOpen     (connection established)
#   onReceiveText  = onMessage  (text frame received)
#
# NO exec. NO save. NO quit. This file only implements the five allowlisted
# actions. Adding an action is one line in ALLOWED_ACTIONS plus a
# handle_<action> function.
#
# This file is documentation-as-code. It is NOT imported by the FastAPI
# service.

import json

# THE plugin-side allowlist — single source of truth on this side.
# Referenced by validation and dispatch below. Do not scatter action-name
# string literals. Adding an action later (e.g. write_script): add one
# string here, plus a handle_<action> function.
ALLOWED_ACTIONS = frozenset(
    (
        "create_op",
        "set_par",
        "connect",
        "list_ops",
        "delete_op",
        # "write_script",  # later phase — do not implement now
    )
)

NETWORK_ERRORS_CAP = 10


def collect_debug(affected=None):
    """Build the contract debug block for every reply.

    - op_errors: t.errors() on the affected op, if it still exists
    - cook_ms: t.cookTime if available (getattr; do not assume the member)
    - network_errors: project-wide scan, capped at NETWORK_ERRORS_CAP
    """
    debug = {}
    op_errors = []
    if affected is not None:
        try:
            errs = affected.errors()
            if errs:
                if isinstance(errs, (list, tuple)):
                    op_errors = [str(item) for item in errs]
                else:
                    op_errors = [str(errs)]
        except Exception:
            pass
        cook_ms = getattr(affected, "cookTime", None)
        if cook_ms is not None:
            debug["cook_ms"] = cook_ms
    debug["op_errors"] = op_errors
    debug["network_errors"] = _collect_network_errors()
    return debug


def _walk_children(node):
    """Recursive children() walk used when root.descendants is unavailable."""
    found = []
    try:
        kids = list(node.children)
    except Exception:
        return found
    for child in kids:
        found.append(child)
        found.extend(_walk_children(child))
    return found


def _collect_network_errors():
    """Scan the network for operator errors.

    Prefer ``root.descendants``. That member is not guaranteed across
    TouchDesigner versions, so the whole scan is wrapped in try/except
    and falls back to a recursive children() walk.
    """
    errors = []
    try:
        # Member availability varies across TD versions.
        nodes = list(root.descendants)
    except Exception:
        try:
            nodes = _walk_children(root)
        except Exception:
            nodes = []
    for o in nodes:
        if len(errors) >= NETWORK_ERRORS_CAP:
            break
        try:
            errs = o.errors()
        except Exception:
            continue
        if not errs:
            continue
        path = getattr(o, "path", "?")
        if isinstance(errs, (list, tuple)):
            text = "; ".join(str(item) for item in errs)
        else:
            text = str(errs)
        errors.append("%s: %s" % (path, text))
    return errors[:NETWORK_ERRORS_CAP]


def handle_create_op(cmd):
    parent = op(cmd["parent_path"])
    created = parent.create(cmd["op_type"], cmd["name"])
    return created, "created %s" % cmd["name"]


def handle_set_par(cmd):
    target = op(cmd["path"])
    getattr(target.par, cmd["par"]).val = cmd["value"]
    return target, "set %s.%s" % (cmd["path"], cmd["par"])


def handle_connect(cmd):
    from_path = cmd.get("from_path", cmd.get("from"))
    source = op(from_path)
    dest = op(cmd["to_path"])
    dest.inputConnectors[int(cmd.get("input_index", 0))].connect(source)
    return dest, "connected"


def handle_list_ops(cmd):
    parent = op(cmd["path"])
    names = [child.name for child in parent.children]
    return parent, ", ".join(names)


def handle_delete_op(cmd):
    target = op(cmd["path"])
    target.destroy()
    return None, "deleted"


def _dispatch(cmd):
    """Run the handler named handle_<action>. ALLOWED_ACTIONS is the gate."""
    action = cmd["action"]
    handler = globals().get("handle_" + action)
    if handler is None:
        raise RuntimeError("no handler for allowed action %s" % action)
    return handler(cmd)


def _send(webSocketDAT, reply):
    webSocketDAT.sendText(json.dumps(reply))


def onConnect(webSocketDAT):
    """onConnect = onOpen. Send the pairing register as the first message."""
    payload = {
        "action": "register",
        "token": str(webSocketDAT.par.Token),
        "session": str(webSocketDAT.par.Session),
    }
    webSocketDAT.sendText(json.dumps(payload))


def onDisconnect(webSocketDAT):
    """Disconnect is normal; the service drops the session and keeps running."""
    return


def onReceiveText(webSocketDAT, data):
    """onReceiveText = onMessage. Dispatch an allowlisted command and reply."""
    try:
        cmd = json.loads(data)
    except Exception:
        _send(
            webSocketDAT,
            {"ok": False, "error": "invalid JSON", "debug": collect_debug(None)},
        )
        return

    if not isinstance(cmd, dict):
        _send(
            webSocketDAT,
            {
                "ok": False,
                "error": "command must be a JSON object",
                "debug": collect_debug(None),
            },
        )
        return

    action = cmd.get("action")
    if action not in ALLOWED_ACTIONS:
        # Ignore non-command messages (register ack from the server is
        # {"ok": true, "session_id": "..."} and has no action).
        if action is None or action == "register":
            return
        _send(
            webSocketDAT,
            {
                "ok": False,
                "error": "action %r is not allowed" % (action,),
                "debug": collect_debug(None),
            },
        )
        return

    affected = None
    try:
        affected, result = _dispatch(cmd)
        _send(
            webSocketDAT,
            {"ok": True, "result": result, "debug": collect_debug(affected)},
        )
    except Exception as exc:
        _send(
            webSocketDAT,
            {
                "ok": False,
                "error": str(exc),
                "debug": collect_debug(affected),
            },
        )


def onReceiveBinary(webSocketDAT, data):
    return


def onReceivePing(webSocketDAT, data):
    return


def onReceivePong(webSocketDAT, data):
    return
