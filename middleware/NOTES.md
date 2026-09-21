# TD Integration Notes (build 2023.12480, first live session)

## Gotchas hit and fixed — the plugin packaging spec
1. WebSocket DAT ships with Active OFF. The reusable component must default Active to On.
2. This build's callback names are onConnect / onReceiveText / onReceivePing.
   Current builds use onOpen / onMessage. Ship BOTH in component callbacks —
   TD calls the ones it knows.
3. WebSocket DAT defaults to SERVER mode (blank Network Address = grayed out).
   Client mode = fill Network Address (e.g. 127.0.0.1) + port. Never assume the mode.
4. TD connects at path "/" — middleware must accept any WS path (catch-all route),
   not only /ws.
5. Contract drift: the JSON `connect` field is `from`, not `from_path`; `to_path` is correct.
   TD executor should be generated from the Pydantic schema to prevent contract drift.
6. TD's textport (Alt+T) is the debugging surface: callback exceptions appear
   there, not in the middleware logs. Check both sides.

## Gotcha #7 — Component does not dial on load
WebSocket DAT in client mode does not auto-retry after a failed or absent connection at startup. The register handshake never fires, and TD gives no error — the failure is silent.
- v1 workaround: pulse the `Active` parameter if `GET /sessions` is empty.
- v2 fix (planned): Timer CHOP watchdog checking connection state every ~2s, re-pulsing `Active` on disconnect. Add a `Session` custom param so the middleware can distinguish multiple TD instances.

(2026-09-20: .tox may also save with Active off; fresh-file acceptance test registered only after pulsing Active off/on.)

## Verified working
All five actions exercised end-to-end: create_op, list_ops, set_par, connect,
delete_op — with structured debug (errors, cook_ms) flowing back per reply.
- Reusability acceptance test passed 2026-09-20: brand-new .toe + dragged
  TDAgent.tox + Active pulse → session registered, all five actions available.

get_op_info added for agent read-back verification (item 6 prerequisite); read-only by design.
