# Roadmap

1. Commit `TDAgent.tox` + [[03 Failures/Component doesn't dial on load — no auto-retry|gotcha #7]] (2026-09-20, done via Cursor prompt)
2. Swap old hand-built `websocket1` for component instance in `RAG.toe` (manual) — see [[02 Sessions/2026-09-20 — bridge and component|session note]]
3. Render deploy: paid always-on instance, `wss://`, `PAIRING_TOKEN` in env vars — gated on [[01 Decisions/ADR-005 component-first formalization|ADR-005]]'s condition (component hardened locally first)
4. Component v2: reconnect watchdog ([[03 Failures/Component doesn't dial on load — no auto-retry|failure detail]]), Address/Port/Token/Session parameters, dual callback naming ([[03 Failures/Callbacks never fire — build 2023 naming|onConnect+onOpen, onReceiveText+onMessage]])
5. Agent loop: 27-line loop + `td_create_op`/`td_set_par`/`td_list_ops` tools → first NL build ("base fx with circleTOP+levelTOP, opacity 0.5, verify")
6. Corpus: MIDI system Python → technique `.md`s with YAML front-matter (`id`, `ops_required`, `key_params`, `verification`) — see [[04 Taxonomy/midi system ingestion (planned)|taxonomy note]]
7. UI: tool-call feed, render snapshots, "Build this" button, PWA
8. Context: [twozero.ai](https://twozero.ai) is a commercial product in this category — differentiation is open + governed + eval-backed. Comparison benchmark planned (same prompts, both systems).
