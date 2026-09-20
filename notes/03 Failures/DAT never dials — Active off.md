---
tags: [failure, td-bridge]
---

# DAT never dials — Active off

**Symptom:** `GET /sessions` returns empty. Zero `[WS-DEBUG]` lines in the middleware log. TD textport is clean — no errors at all.

**Environment:** TD 2023.12480, fresh `.toe`, WebSocket DAT freshly added.

**Evidence:** Complete silence on both sides. Not an error — an absence.

**Root cause:** The WebSocket DAT ships with `Active` OFF by default. A DAT with Active off never attempts a connection, so there's nothing to fail — which is why there's no error anywhere to find.

**Fix:** Toggle `Active` to On on the DAT's parameters page.

**Prevention:** [[../01 Decisions/ADR-005 component-first formalization|The TDAgent component]] should default `Active` to On, or — better — visibly indicate connection state on the component itself so "nothing happening" is never silently ambiguous with "working correctly."

**Related:** [[../01 Decisions/ADR-002 TD connects out]]
