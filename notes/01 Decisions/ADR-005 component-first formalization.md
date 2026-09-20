# ADR-005: Component-first formalization

Formalize the TD side as a reusable component (`TDAgent.tox`) *before* hosting the middleware on Render.

**Reasoning:** Render deploy introduces its own new variables — TLS, reverse proxy, instance sleeping/waking — and those need to be debugged against a TD side that is already known-good. Debugging two unknowns at once (a fragile hand-built `websocket1` node *and* a new hosting environment) makes it impossible to tell which layer a failure belongs to.

Sequence: harden the component locally against `localhost` first (all seven [[../03 Failures/index|failures]] happened here), *then* move to hosted infrastructure.

**Related:** [[ADR-002 TD connects out]]. Roadmap item 3 ([[../05 Roadmap|Roadmap]]) — Render deploy — is deliberately sequenced after this ADR's condition is met.
