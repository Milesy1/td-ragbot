---
tags: [failure, td-bridge]
---

# Component doesn't dial on load — no auto-retry

**Symptom:** On opening a `.toe` file, the TDAgent component's connection attempt fails silently. No session appears, and nothing tries again on its own.

**Environment:** Client-mode WebSocket DAT inside `TDAgent.tox`, `.toe` file load.

**Evidence:** No error — the connection simply never (re-)establishes after the first failed attempt at file-open time (e.g. middleware not yet running when TD loads).

**Root cause:** Client-mode DATs in TD do not auto-retry a failed connection. If the middleware isn't up yet at the moment the `.toe` loads, the component is left permanently disconnected until manually re-pulsed.

**Fix (interim, until v2):** Manually pulse the `Active` parameter off then on again if `/sessions` is empty after opening a project.

**Fix (required for v2 — [[../05 Roadmap|Roadmap]] item 4):** A reconnect watchdog — a Timer CHOP checking socket state on a ~2s interval, automatically re-pulsing `Active` when disconnected.

**Prevention:** Until the watchdog ships, install/usage docs must explicitly say: *"pulse Active if `/sessions` is empty."* This is a known, accepted gap, not a mystery to re-debug each time.

**Related:** [[DAT never dials — Active off]] (same parameter, different trigger condition)
