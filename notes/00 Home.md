# td-agent

An agentic AI system that builds TouchDesigner networks from natural language.

## Components
1. **TD RagBot** (td.mileswaite.net) — RAG Q&A over TD docs. Hybrid retrieval (`all-MiniLM-L6-v2` embeddings + BM25, RRF fusion), Qdrant Cloud, Groq `llama-3.1-8b-instant` generation.
2. **td-middleware** — FastAPI chokepoint, WebSocket server, 5-action allowlist (`create_op`, `set_par`, `connect`, `list_ops`, `delete_op`), Pydantic validation, JSONL audit log, 25 pytest tests.
3. **TDAgent.tox** — reusable TD component (WebSocket DAT client mode + callbacks, register handshake with pairing token).

## Decisions
[[01 Decisions/ADR-001 middleware chokepoint]] · [[01 Decisions/ADR-002 TD connects out]] · [[01 Decisions/ADR-003 fixed command contract]] · [[01 Decisions/ADR-004 one repo monorepo]] · [[01 Decisions/ADR-005 component-first formalization]]

## Sessions
[[02 Sessions/2026-09-20 — bridge and component]]

## Failures
[[03 Failures/DAT never dials — Active off]] · [[03 Failures/Callbacks never fire — build 2023 naming]] · [[03 Failures/Connection arrives but no register — missing custom parameters]] · [[03 Failures/TD connects at root path — ws route mismatch]] · [[03 Failures/connect command rejected — schema field name drift]] · [[03 Failures/PowerShell mangles curl JSON quoting]] · [[03 Failures/Component doesn't dial on load — no auto-retry]]

## Taxonomy
[[04 Taxonomy/corpus design]] · [[04 Taxonomy/midi system ingestion (planned)]]

## Roadmap
[[05 Roadmap]]
