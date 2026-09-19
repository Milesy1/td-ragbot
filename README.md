# TD RagBot

A RAG bot for TouchDesigner documentation, built on a fully local stack — zero ongoing cost, no data leaving the machine. Each file follows a higher standard than the earlier `miles-rag` build: type hints, docstrings, and real error handling throughout.

## Stack

- **Ollama** — local LLM (`llama3.1`) + embeddings (`nomic-embed-text`), OpenAI-compatible API at `localhost:11434`
- **Qdrant** — local vector store, run via Docker (`--restart unless-stopped`, persistent volume — survives restarts)
- **Python RAG pipeline** — reusing concepts from `miles-rag` (chunking, hybrid retrieval), rebuilt against real Qdrant storage instead of in-memory lists

## Built so far

- **`document.py`** — `Document` class: `content`, `source`, `header_title`, `doc_category`. Raises `ValueError` on empty content.
- **`chunk_text.py`** — `split_by_headers()`: splits markdown by headers into `(header_title, section_text)` pairs. `chunk_section()`: character-count/overlap chunking within a section, with error handling for invalid `chunk_size`/`overlap`.
- **`embed.py`** — `embed_text()`: 768-dim embeddings via Ollama's `nomic-embed-text`, with error handling for empty input and connection failures.
- **`ingest.py`** — the orchestrator: walks a real folder of `.md` files, splits by header, chunks, wraps each chunk in a `Document`, embeds, and stores into Qdrant (`touchdesigner_docs` collection). Idempotent collection creation. Verified: 101 real chunks ingested from `wiki`.
- **`retrieval.py`** — `retrieve()`: semantic search against real stored Qdrant vectors via `query_points()`.
- **`keyword_search.py`** — `keyword_search()`: lexical relevance via `client.scroll()` + keyword overlap scoring.
- **`hybrid_search.py`** — `rrf_combine()`: fuses semantic + keyword rankings via Reciprocal Rank Fusion (rank position, not raw score, since the two scales are incompatible). `hybrid_search()`: runs both searches and returns the fused top-k. Verified: results genuinely more diverse than semantic-only search.
- **`eval.py`** — `run_eval()`: a real eval harness — 5 test queries against the ingested `wiki` docs, checking whether the expected keyword appears in the top hybrid result. Result: 5/5 passed.
- **`model_search.py`** (side-quest) — searches Hugging Face's Model Hub programmatically for candidate embedding models, so alternatives to `nomic-embed-text` can be compared before scaling to the full corpus.

See `flows/` for a step-by-step trace of each file's logic, including error paths.

## Content source

Existing cleaned TouchDesigner documentation corpus (`docs_clean/wiki`, `forum`, `github_repos`, `introduction-book`, `pauric_freeman`). Currently only `wiki` has been ingested; full-corpus ingestion is a planned next step.

## Remaining work

- Implement Corrective RAG (CRAG) — retrieval-quality grading + corrective actions (refine/discard+search/blend), likely as a LangGraph workflow
- Ingest the full corpus (not just `wiki`)

## Related project

A separate agent (own repo, TBD name) will reason over tools to actually build TouchDesigner networks — creating operators, setting parameters, wiring connections — using this RAG bot's retrieval as its knowledge source. That project starts once CRAG is complete here.
