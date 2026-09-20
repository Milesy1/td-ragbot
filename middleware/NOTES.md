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

## Verified working
All five actions exercised end-to-end: create_op, list_ops, set_par, connect,
delete_op — with structured debug (errors, cook_ms) flowing back per reply.
