# TD RagBot

A RAG bot for TouchDesigner documentation, built on a fully local stack — zero ongoing cost, no data leaving the machine.

## Stack

- **Ollama** — local LLM (generation) + embeddings, OpenAI-compatible API at `localhost:11434`
- **Qdrant** — local vector store, run via Docker
- **Python RAG pipeline** — reusing patterns from `miles-rag` (chunking, hybrid retrieval, LangGraph orchestration), adapted for local models

## Goal

Apply everything built in `miles-rag` (ingestion, chunking, hybrid retrieval, LangGraph, evals) to a real corpus — TouchDesigner wiki documentation — and layer Corrective RAG (CRAG) on top. New files, new features per file, broadening skills rather than repeating the `miles-rag` build.

## Content source

Existing cleaned TouchDesigner documentation corpus (wiki pages, forum posts, introduction book) — reused as real ingestible content.

## Status

Just started — setting up the local Ollama + Qdrant stack.
