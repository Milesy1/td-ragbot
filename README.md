# TD RagBot

A RAG bot for TouchDesigner documentation. Dense embeddings and a MiniLM cross-encoder run locally (`sentence-transformers`). Lexical search is BM25 sparse vectors in Qdrant (IDF on the server). Generation is streamed from Groq (`llama-3.1-8b-instant`).

This repo contains two systems: the RAG chatbot (public, read-only, deployed to Render) and td-middleware (a local/private control plane with write access to TouchDesigner). Two systems, two trust levels.

## Stack

- **sentence-transformers** — dense embed (`all-MiniLM-L6-v2`, 384-d) and rerank (`ms-marco-MiniLM-L-6-v2`). Falls back to Hugging Face Inference if the local model cannot load. Set `HUGGINGFACE_TOKEN` for Hub downloads.
- **Groq** — hosted LLM (`llama-3.1-8b-instant` by default). Set `GROQ_API_KEY`. Follow-up questions are rewritten into standalone search queries before retrieval.
- **Qdrant** — named dense + BM25 sparse vectors. Cloud via `QDRANT_URL` / `QDRANT_API_KEY`.
- **FastAPI** — chat UI + SSE `/api/chat/stream`.

Shared settings live in `config.py`.

## Retrieval

1. Route corpora: wiki + book by default; github / interview only when the query looks like plugin/C++/Unreal/TouchEngine or Pauric.
2. Dense search and BM25 search in parallel, fused with RRF.
3. Cross-encoder rerank of the fused candidates.
4. If the top rerank score is weak, the bot says it could not find reliable docs instead of guessing.

Vendor trees (rapidjson, translation files, VS project dumps) are skipped at ingest.

## Ingest

```
python ingest.py --recreate path/to/docs_clean/wiki
python ingest.py path/to/docs_clean/wiki_full
python ingest.py path/to/docs_clean/github_repos
python ingest.py path/to/docs_clean/introduction-book
python ingest.py path/to/docs_clean/pauric_freeman
```

Forum is intentionally not ingested yet.

## Eval

`python eval.py` checks gold **sources** (e.g. preferences must hit `Preferences` / `Dialogs_Preferences`), not generic substrings in chunk text.

## Remaining work

- Full Corrective RAG (grade/refine/web-search) if wiki misses keep showing up
- Forum ingest after routing/rerank prove stable
