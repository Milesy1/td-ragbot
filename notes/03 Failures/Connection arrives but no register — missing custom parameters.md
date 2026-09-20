---
tags: [failure, td-bridge]
---

# Connection arrives but no register — missing custom parameters

**Symptom:** Socket connects, callbacks fire, but no session ever appears in `GET /sessions`. Middleware log shows the connection closing "before first message."

**Environment:** TD 2023.12480, callbacks DAT correctly named ([[Callbacks never fire — build 2023 naming|see prior failure]]).

**Evidence:** TD textport shows `tdAttributeError` when the callback executes. Middleware sees a connection open then immediately close with no payload.

**Root cause:** The callback code referenced `par.Token` and `par.Session` as custom parameters on the DAT — but those custom parameters were never actually added to the DAT. The callback crashes the instant it tries to read them, before it can send the register handshake.

**Fix:** Add the two custom parameters (`Token`, `Session`) to the DAT explicitly before pasting in callback code that references them.

**Prevention:** Custom parameters must ship as part of the `TDAgent.tox` component definition itself, not as a manual step in install instructions — a component's callback code should never reference a parameter the component didn't already create.

**Related:** [[Callbacks never fire — build 2023 naming]], [[../01 Decisions/ADR-005 component-first formalization]]
