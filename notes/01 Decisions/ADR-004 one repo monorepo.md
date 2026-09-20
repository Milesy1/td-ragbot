# ADR-004: One repo, monorepo

`middleware/` and `plugin/` live inside the existing `td-ragbot` repo, alongside the RAG chatbot, rather than as a standalone `td-agent` repo.

**Reasoning:** the two systems aren't independent yet — one consumer (this project) needs both, and premature separation adds repo/CI/versioning overhead with no current benefit.

**Exit condition:** extract to a standalone `td-agent` repo only when a second consumer exists — i.e. when something other than this project's own web UI needs to drive the middleware.

**Related:** [[ADR-001 middleware chokepoint]]
