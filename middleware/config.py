"""Environment-driven settings for the TD agent middleware.

Reads ``os.environ`` directly — no settings framework. Tests set
``PAIRING_TOKEN`` (and optionally ``AUDIT_LOG_PATH``) before importing the app.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def is_production() -> bool:
    """Return True when running on Render or an explicit production env."""
    if os.environ.get("RENDER"):
        return True
    env = (os.environ.get("ENVIRONMENT") or os.environ.get("APP_ENV") or "").lower()
    return env == "production"


@dataclass(frozen=True)
class Settings:
    """Typed runtime settings loaded from the environment."""

    bind_host: str
    port: int
    pairing_token: str
    audit_log_path: str
    cmd_timeout_seconds: float


def load_settings() -> Settings:
    """Load settings from the environment.

    ``PAIRING_TOKEN`` has no default. In production (Render sets ``RENDER``,
    or ``ENVIRONMENT`` / ``APP_ENV`` is ``production``) a missing or empty
    token raises ``RuntimeError`` immediately. In local/dev the value is
    still read from the environment (empty string if unset); tests set it.
    """
    token = os.environ.get("PAIRING_TOKEN", "")
    if is_production() and not token.strip():
        raise RuntimeError(
            "PAIRING_TOKEN is required in production "
            "(RENDER is set, or ENVIRONMENT/APP_ENV is 'production')"
        )
    return Settings(
        bind_host=os.environ.get("BIND_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        pairing_token=token,
        audit_log_path=os.environ.get("AUDIT_LOG_PATH", "./audit.jsonl"),
        cmd_timeout_seconds=float(os.environ.get("CMD_TIMEOUT_SECONDS", "10")),
    )
