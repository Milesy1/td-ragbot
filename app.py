# Stage 9: app - FastAPI backend serving the chat UI. Wires
# hybrid_search() (retrieval) + Groq-hosted llama-3.1 (generation,
# streamed) together into a real RAG endpoint, deployable on Render
# since Groq is a hosted API, not a local model server. Supports
# multi-turn conversation - the client sends the full message history,
# retrieval uses only the latest question.
import asyncio
import json
import os
import traceback
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

from config import (
    COLLECTION_NAME,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL_LABEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    MAX_HISTORY_ITEMS,
    MAX_HISTORY_MESSAGES,
    MAX_MESSAGE_CONTENT_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_TOP_K,
    MIN_TOP_K,
    get_qdrant_client,
)
from hybrid_search import hybrid_search

app = FastAPI(title="TD RagBot")

llm_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_STREAM_DONE = object()

SYSTEM_PROMPT = (
    "You are a TouchDesigner documentation assistant. Answer the user's "
    "question using ONLY the provided context below. Use Markdown "
    "formatting (headers, bullet points, fenced code blocks for any "
    "TouchDesigner Python/expression syntax). If the context doesn't "
    "contain the answer, say so plainly rather than guessing. The "
    "conversation history is provided so you can understand follow-up "
    "questions that refer back to earlier messages.\n\n"
    "Context:\n"
)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CONTENT_LENGTH)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=MIN_TOP_K, le=MAX_TOP_K)
    history: list[Message] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def build_context_and_sources(query: str, top_k: int) -> tuple[str, list[dict]]:
    """Run hybrid_search and build both the LLM context string and the
    structured source list the frontend displays."""
    results = hybrid_search(query, top_k=top_k)

    context = "\n\n---\n\n".join(
        f"[{payload['header_title']}]\n{payload['content']}"
        for payload, _ in results
    )

    sources = [
        {
            "header_title": payload["header_title"],
            "doc_category": payload["doc_category"],
            "source": payload["source"],
            "score": round(score, 4),
        }
        for payload, score in results
    ]

    return context, sources


def _empty_stats() -> dict:
    return {
        "chunk_count": None,
        "categories": [],
        "source_file_count": None,
        "source_file_count_is_estimate": False,
        "status": None,
        "embedding_model": EMBEDDING_MODEL_LABEL,
    }


@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
def serve_ui() -> FileResponse:
    """
    Serve the chat UI's index page.

    Explicitly supports HEAD as well as GET - Starlette/FastAPI does
    NOT auto-add HEAD support for a GET-only route (unlike some other
    frameworks), and uptime monitors (e.g. UptimeRobot) send HEAD
    requests by default, which was causing false "down" alerts (405
    Method Not Allowed) even though the site was genuinely reachable.
    """
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/about", include_in_schema=False)
def serve_about() -> FileResponse:
    """Serve the About page - architecture, provenance, and honest
    limitations, written for a human reader rather than a developer."""
    return FileResponse(STATIC_DIR / "about.html")


@app.get("/api/stats")
def get_stats() -> dict:
    """
    Return live metadata from Qdrant: total chunk count, distinct source
    file count, doc_category values present, collection health, and the
    embedding model in use. Powers the header ticker showing real
    corpus coverage.
    """
    try:
        client = get_qdrant_client()
        info = client.get_collection(COLLECTION_NAME)
        chunk_count = info.points_count
        status = info.status.value if hasattr(info.status, "value") else str(info.status)

        # Scroll a sample of payloads to collect distinct doc_category
        # and source values. Sampling (not a full scan) keeps this cheap
        # even as the collection grows into the tens of thousands of
        # points - source-file count from a sample is an estimate, not
        # exact, once the corpus is larger than the sample size.
        categories = set()
        sources = set()
        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=2000,
            with_payload=["doc_category", "source"],
        )
        for point in points:
            payload = point.payload or {}
            cat = payload.get("doc_category")
            src = payload.get("source")
            if cat:
                categories.add(cat)
            if src:
                sources.add(src)

        return {
            "chunk_count": chunk_count,
            "categories": sorted(categories),
            "source_file_count": len(sources),
            "source_file_count_is_estimate": chunk_count is not None and chunk_count > len(points),
            "status": status,
            "embedding_model": EMBEDDING_MODEL_LABEL,
        }
    except Exception as e:
        print(f"[get_stats] error: {e}\n{traceback.format_exc()}")
        return _empty_stats()


def _next_llm_chunk(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return _STREAM_DONE


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Stream a RAG answer token-by-token as Server-Sent Events.

    Retrieval uses only the latest question (request.query) - what to
    search for doesn't depend on prior turns. Generation uses the full
    conversation history (request.history) so follow-up questions that
    refer back to earlier turns ("what about for a COMP?") are understood.

    First event carries the retrieved sources (so the UI can show them
    immediately), followed by a stream of text-delta events as the LLM
    generates, then a final "done" event.

    Blocking HF/Qdrant/Groq calls run in a worker thread so one slow
    request does not stall the event loop.
    """
    if not request.query.strip():
        async def empty_stream():
            yield _sse({"type": "error", "text": "Please enter a question."})

        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def event_stream():
        try:
            context, sources = await asyncio.to_thread(
                build_context_and_sources, request.query, request.top_k
            )
        except Exception as e:
            print(f"[chat_stream] retrieval error: {e}\n{traceback.format_exc()}")
            yield _sse({"type": "error", "text": "Retrieval failed. Please try again."})
            return

        yield _sse({"type": "sources", "sources": sources})

        if not sources:
            msg = "I couldn't find anything relevant in the TouchDesigner docs for that."
            yield _sse({"type": "delta", "text": msg})
            yield _sse({"type": "done"})
            return

        # Concatenate context rather than str.format so curly braces in
        # retrieved TouchDesigner Python/expressions cannot KeyError.
        capped_history = request.history[-MAX_HISTORY_MESSAGES:]
        messages = [{"role": "system", "content": SYSTEM_PROMPT + context}]
        messages.extend({"role": m.role, "content": m.content} for m in capped_history)
        messages.append({"role": "user", "content": request.query})

        delta_count = 0
        try:
            stream = await asyncio.to_thread(
                lambda: llm_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    stream=True,
                )
            )
            iterator = iter(stream)
            while True:
                chunk = await asyncio.to_thread(_next_llm_chunk, iterator)
                if chunk is _STREAM_DONE:
                    break
                delta = chunk.choices[0].delta.content
                if delta:
                    delta_count += 1
                    yield _sse({"type": "delta", "text": delta})

            if delta_count == 0:
                print("[chat_stream] Groq stream completed with zero content deltas")
                yield _sse({
                    "type": "error",
                    "text": "The model returned an empty response. Please try again.",
                })

        except Exception as e:
            print(f"[chat_stream] generation error: {e}\n{traceback.format_exc()}")
            yield _sse({"type": "error", "text": "Generation failed. Please try again."})

        yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # Prevent Render's/any intermediary proxy from buffering the
            # stream, which can otherwise deliver everything at once (or
            # drop it) instead of true incremental streaming.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8420))
    uvicorn.run(app, host="0.0.0.0", port=port)
