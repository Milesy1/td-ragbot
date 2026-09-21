"""get_op_info — paste-in handler body for TD callbacks (read-only).

TD calls ``handle_get_op_info(cmd)`` and relies on the global ``op``.
Tests inject ``op_lookup``. Adding ``get_op_info`` to the TD ALLOWED /
ALLOWED_ACTIONS set is one line the user will do.

This file is the handler body to paste; it is not imported by FastAPI
(TD-only names such as ``op`` are resolved at call time).
"""


def handle_get_op_info(cmd, op_lookup=None):
    """Return name, type, pars, cook time, and wiring for one operator.

    ``cmd`` is a dict with ``action``, optional ``session``, and ``path``.
    ``op_lookup`` defaults to the TouchDesigner global ``op``.
    """
    lookup = op_lookup or op
    path = cmd["path"]
    target = lookup(path)
    if target is None:
        return {
            "ok": False,
            "result": None,
            "op_errors": ["op not found: %s" % path],
            "debug": {},
        }

    pars = {}
    for p in target.pars():
        try:
            pars[p.name] = p.eval()
        except Exception as e:
            pars[p.name] = "<unevaluable: %s>" % e

    result = {
        "name": target.name,
        "optype": target.type,
        "pars": pars,
        "cook_ms": target.cookTime,
        "inputs": [i.name if i else None for i in target.inputs],
        "outputs": [o.name if o else None for o in target.outputs],
        "children": len(target.children),
    }
    return {
        "ok": True,
        "result": result,
        "op_errors": [],
        "debug": {},
    }
