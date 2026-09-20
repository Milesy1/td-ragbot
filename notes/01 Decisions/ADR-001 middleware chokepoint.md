# ADR-001: Middleware as chokepoint

Governance (allowlist, audit log) is enforced architecturally, not in prompts. The FastAPI middleware sits between the agent loop and TouchDesigner as the single point every command must pass through — no direct agent-to-TD path exists.

Same pattern used in [[../aria|ARIA]]'s ERP agent middleware: the agent is trusted to *decide*, never trusted to *execute* unchecked.

Forced by nothing directly (this was the starting premise), but validated by every failure in [[../03 Failures/index|03 Failures]] that happened *inside* the middleware boundary rather than around it — the boundary held.

**Related:** [[ADR-002 TD connects out]], [[ADR-003 fixed command contract]]
