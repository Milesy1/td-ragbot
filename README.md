# TD RagBot

A RAG bot for TouchDesigner documentation. Retrieval runs against Qdrant; embeddings come from Hugging Face Inference (`all-MiniLM-L6-v2`, 384-d); generation is streamed from Groq (`llama-3.1-8b-instant`). Each file uses type hints, docstrings, and real error handling.

## Stack

- **Hugging Face Inference API** — embeddings (`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions). Set `HUGGINGFACE_TOKEN`.
- **Groq** — hosted LLM (`llama-3.1-8b-instant` by default, override with `GROQ_MODEL`). Set `GROQ_API_KEY`.
- **Qdrant** — vector store. Local Docker (`http://localhost:6333`) or Qdrant Cloud via `QDRANT_URL` / `QDRANT_API_KEY`.
- **FastAPI** — chat UI + SSE `/api/chat/stream` in `app.py`.

Shared settings live in `config.py` so ingest and query cannot drift.

## Pipeline

- **`document.py`** — `Document` class: `content`, `source`, `header_title`, `doc_category`. Raises `ValueError` on empty or whitespace-only content.
- **`chunk_text.py`** — `split_by_headers()`: CommonMark ATX headers only; keeps preamble; ignores `#` inside fenced code blocks. `chunk_section()`: overlapping chunks that break on whitespace.
- **`embed.py`** — `embed_text()`: 384-d vectors via HF Inference, retrying only 429/5xx/timeouts.
- **`ingest.py`** — walks a folder of `.md` files, chunks, embeds, batch-upserts into `touchdesigner_docs`. Deterministic UUID point IDs (`uuid5` of relative source path + chunk index). Creates a text index on `content` for keyword search. Usage: `python ingest.py path/to/docs_clean/wiki` (or set `DOCS_FOLDER`).
- **`retrieval.py`** — `retrieve()`: semantic search via `query_points()`.
- **`keyword_search.py`** — `keyword_search()`: text-index filter (paginated scroll fallback) + keyword overlap scoring.
- **`hybrid_search.py`** — runs semantic + keyword search in parallel, fuses with Reciprocal Rank Fusion.
- **`eval.py`** — recall@k harness: expected phrase must appear in header, source, or content of any top-k hit.
- **`app.py`** — FastAPI UI + streaming RAG. History roles are allow-listed (`user`/`assistant`); `top_k` and payload sizes are capped; context is concatenated (not `str.format`) so TD `{expressions}` cannot break the prompt.
- **`model_search.py`** (side-quest) — searches Hugging Face's Model Hub for candidate embedding models.

See `flows/` for a step-by-step trace of each file's logic, including error paths. Those notes predate some of the search/ID changes above; the Python modules are the source of truth.

## Content source

Existing cleaned TouchDesigner documentation corpus (`docs_clean/wiki`, `forum`, `github_repos`, `introduction-book`, `pauric_freeman`).

**Re-ingest after this change.** Point IDs switched from 64-bit ints (unsafe over JSON) to UUIDs, and source paths are now repo-relative. Old points will not be updated in place — recreate or overwrite the collection, then:

```
python ingest.py path/to/docs_clean/wiki
```

## Remaining work

- Implement Corrective RAG (CRAG) — retrieval-quality grading + corrective actions (refine/discard+search/blend), likely as a LangGraph workflow
- Ingest the full corpus (not just `wiki`)

## Related project

A separate agent (own repo, TBD name) will reason over tools to actually build TouchDesigner networks — creating operators, setting parameters, wiring connections — using this RAG bot's retrieval as its knowledge source. That project starts once CRAG is complete here.
