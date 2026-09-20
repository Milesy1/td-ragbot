---
tags: [failure, td-bridge]
---

# TD connects at root path — ws route mismatch

**Symptom:** TD's connection appears to succeed, but the middleware's `/ws` handler never sees it.

**Environment:** Middleware originally listened on `/ws` only, matching the intended URL `ws://localhost:8000/ws`.

**Evidence:** Connection logged at the ASGI server level; never reaches the intended route handler.

**Root cause:** TD connected at path `/` (root), not `/ws` — a URL configuration mismatch on the DAT side. The middleware had no handler at `/`, so the connection was accepted at the transport level but never routed anywhere useful.

**Fix:** Middleware now uses a catch-all route: `@app.websocket("/{full_path:path}")`, so any path TD happens to dial still reaches the same handler.

**Prevention:** The catch-all is itself the prevention — it makes the exact URL path TD is configured with a non-issue. Still worth setting `TDAgent.tox`'s default URL correctly so this class of confusion doesn't recur even though the middleware now tolerates it.

**Related:** [[../01 Decisions/ADR-002 TD connects out]]
