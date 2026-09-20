"""Pytest bootstrap: pairing token, audit path, and middleware import path.

Import style matches ``uvicorn app:app`` from the middleware directory
(``from app import app``, ``from schemas import Command``). This file
puts ``middleware/`` at the front of ``sys.path`` so the same imports
work when pytest is launched from the repo root.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["PAIRING_TOKEN"] = "test-token"
os.environ.setdefault(
    "AUDIT_LOG_PATH",
    str(Path(tempfile.gettempdir()) / "td-agent-middleware-audit.jsonl"),
)

_MIDDLEWARE = Path(__file__).resolve().parent.parent
_path = str(_MIDDLEWARE)
if sys.path[:1] != [_path]:
    sys.path.insert(0, _path)
