# TD RagBot

A RAG bot for TouchDesigner documentation, built on a fully local stack — zero ongoing cost, no data leaving the machine. Each file follows a higher standard than the earlier `miles-rag` build: type hints, docstrings, and real error handling throughout.

## Stack

- **Ollama** — local LLM (`llama3.1`) + embeddings (`nomic-embed-text`), OpenAI-compatible API at `localhost:11434`
- **Qdrant** — local vector store, run via Docker (`--restart unless-stopped`, persistent volume — survives restarts)
- **Python RAG pipeline** — reusing concepts from `miles-rag` (chunking, hybrid retrieval, LangGraph orchestration), rebuilt against real Qdrant storage instead of in-memory lists

## Built so far

- **`document.py`** — `Document` class: `content`, `source`, `header_title` (which markdown section a chunk came from), `doc_category` (which corpus folder — wiki/forum/etc). Raises `ValueError` on empty content.
- **`chunk_text.py`** — `split_by_headers()`: splits markdown by `#`/`##`/`###` headers into `(header_title, section_text)` pairs. `chunk_section()`: character-count/overlap chunking within a section (fallback for long sections), with error handling for invalid `chunk_size`/`overlap` combinations.
- **`embed.py`** — `embed_text()`: 768-dim embeddings via Ollama's `nomic-embed-text`, with error handling for empty input and connection failures.
- **`ingest.py`** — the orchestrator: walks a real folder of `.md` files, splits by header, chunks, wraps each chunk in a `Document`, embeds, and stores into Qdrant (`touchdesigner_docs` collection) via `PointStruct`/`upsert`. Collection creation is idempotent (checks `collection_exists` first). Verified: 101 real chunks ingested from the `wiki` folder, inspected in the Qdrant dashboard.
- **`retrieval.py`** — `retrieve()`: semantic search against real stored Qdrant vectors via `query_points()` (not the deprecated `search()`), with error handling.
- **`keyword_search.py`** — `keyword_search()`: lexical relevance via `client.scroll()` (pulls stored content directly, no vector comparison) + keyword overlap scoring, same idea as `miles-rag`'s keyword search, adapted for real Qdrant-stored content.
- **`model_search.py`** (side-quest) — searches Hugging Face's Model Hub programmatically (`huggingface_hub`) for candidate embedding models, so alternatives to `nomic-embed-text` can be found and compared before committing to a full corpus ingest.

See `flows/` for a step-by-step trace of each file's logic, including error paths.

## Content source

Existing cleaned TouchDesigner documentation corpus (`docs_clean/wiki`, `forum`, `github_repos`, `introduction-book`, `pauric_freeman`) — reused as real ingestible content. Currently only `wiki` has been ingested; full-corpus ingestion is a planned next step.

## Remaining work

- Combine `retrieve()` + `keyword_search()` via Reciprocal Rank Fusion (hybrid retrieval)
- `eval.py` — real eval harness against actual TouchDesigner queries
- Implement Corrective RAG (CRAG) — retrieval-quality grading + corrective actions, likely as a LangGraph workflow
- Ingest the full corpus (not just `wiki`)
