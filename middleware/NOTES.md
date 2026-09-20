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
5. Contract drift: middleware Pydantic schema names fields from_path/to_path;
   executor must accept both from/to and from_path/to_path. Long-term: generate
   the TD-side dispatcher from the Pydantic models so drift is impossible.
6. TD's textport (Alt+T) is the debugging surface: callback exceptions appear
   there, not in the middleware logs. Check both sides.
7. WebSocket DAT does not reliably dial on its own. On .toe load the connection
   attempt may fire before things are ready and silently fail; client-mode DATs
   do not auto-retry, and the .tox may save with Active off. Evidence: fresh-file
   acceptance test 2026-09-20 — component registered only after manually pulsing
   Active off/on. REQUIRED for v2: an internal reconnect watchdog (Timer CHOP or
   frame script inside TDAgent) that checks socket state every ~2s and re-pulses
   Active when disconnected. Until v2 ships, installation instructions must say:
   "if /sessions shows nothing, pulse Active off/on on the component's websocket1."

## Verified working
All five actions exercised end-to-end: create_op, list_ops, set_par, connect,
delete_op — with structured debug (errors, cook_ms) flowing back per reply.
- Reusability acceptance test passed 2026-09-20: brand-new .toe + dragged
  TDAgent.tox + Active pulse → session registered, all five actions available.
