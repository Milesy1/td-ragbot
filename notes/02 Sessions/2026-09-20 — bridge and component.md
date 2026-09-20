# 2026-09-20 — bridge and component

**Worked:** Built [[../01 Decisions/ADR-001 middleware chokepoint|middleware]] via Cursor agent. Debugged the live bridge end to end — all five actions (`create_op`, `set_par`, `connect`, `list_ops`, `delete_op`) verified with structured debug flowing back (`op_errors`, `cook_ms`). Packaged `TDAgent.tox`, passed a fresh-file acceptance test: new `.toe` + drag component + pulse `Active` → session registered in `GET /sessions`.

**Broke:** [[../03 Failures/DAT never dials — Active off]] · [[../03 Failures/Callbacks never fire — build 2023 naming]] · [[../03 Failures/Connection arrives but no register — missing custom parameters]] · [[../03 Failures/TD connects at root path — ws route mismatch]] · [[../03 Failures/connect command rejected — schema field name drift]] · [[../03 Failures/Component doesn't dial on load — no auto-retry]]

**Next:** Swap the old hand-built `websocket1` node for the component instance in `RAG.toe` ([[../05 Roadmap|Roadmap]] item 2).

**Commits:** `c952872` (middleware), `99c7d5a` (integration notes). TD build: 2023.12480 — callback API on this build is `onConnect`/`onReceiveText`; current builds use `onOpen`/`onMessage`. Component must ship both.
