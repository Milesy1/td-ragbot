# Stage 9: app - FastAPI backend serving the chat UI. Wires
# hybrid_search() (retrieval) + Groq-hosted llama-3.1 (generation,
# streamed) together into a real RAG endpoint, deployable on Render
# since Groq is a hosted API, not a local model server. Supports
# multi-turn conversation - the client sends the full message history,
# retrieval uses only the latest question.
import json
import os
import traceback
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from qdrant_client import QdrantClient

from hybrid_search import hybrid_search

app = FastAPI(title="TD RagBot")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

llm_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
COLLECTION_NAME = "touchdesigner_docs"
EMBEDDING_MODEL_LABEL = "all-MiniLM-L6-v2 · 384d"
stats_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Cap how much history gets sent to the model per request, so cost/latency
# don't grow unbounded as a conversation gets long.
MAX_HISTORY_MESSAGES = 10


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    query: str
    top_k: int = 5
    history: list[Message] = []


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


SYSTEM_PROMPT_TEMPLATE = (
    "You are a TouchDesigner documentation assistant. Answer the user's "
    "question using ONLY the provided context below. Use Markdown "
    "formatting (headers, bullet points, fenced code blocks for any "
    "TouchDesigner Python/expression syntax). If the context doesn't "
    "contain the answer, say so plainly rather than guessing. The "
    "conversation history is provided so you can understand follow-up "
    "questions that refer back to earlier messages.\n\n"
    "Context:\n{context}"
)


@app.get("/")
def serve_ui() -> FileResponse:
    """Serve the chat UI's index page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/stats")
def get_stats() -> dict:
    """
    Return live metadata from Qdrant: total chunk count, distinct source
    file count, doc_category values present, collection health, and the
    embedding model in use. Powers the header ticker showing real
    corpus coverage.
    """
    try:
        info = stats_client.get_collection(COLLECTION_NAME)
        chunk_count = info.points_count
        status = info.status.value if hasattr(info.status, "value") else str(info.status)

        # Scroll a sample of payloads to collect distinct doc_category
        # and source values. Sampling (not a full scan) keeps this cheap
        # even as the collection grows into the tens of thousands of
        # points - source-file count from a sample is an estimate, not
        # exact, once the corpus is larger than the sample size.
        categories = set()
        sources = set()
        points, _ = stats_client.scroll(
            collection_name=COLLECTION_NAME,
            limit=2000,
            with_payload=["doc_category", "source"],
        )
        for point in points:
            cat = point.payload.get("doc_category")
            src = point.payload.get("source")
            if cat:
                categories.add(cat)
            if src:
                sources.add(src)

        return {
            "chunk_count": chunk_count,
            "categories": sorted(categories),
            "source_file_count": len(sources),
            "source_file_count_is_estimate": chunk_count > len(points),
            "status": status,
            "embedding_model": EMBEDDING_MODEL_LABEL,
        }
    except Exception as e:
        print(f"[get_stats] error: {e}\n{traceback.format_exc()}")
        return {"chunk_count": None, "categories": []}


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Stream a RAG answer token-by-token as Server-Sent Events.

    Retrieval uses only the latest question (request.query) - what to
    search for doesn't depend on prior turns. Generation uses the full
    conversation history (request.history) so follow-up questions that
    refer back to earlier turns ("what about for a COMP?") are understood.

    First event carries the retrieved sources (so the UI can show them
    immediately), followed by a stream of text-delta events as the LLM
    generates, then a final "done" event.
    """
    if not request.query.strip():
        def empty_stream():
            yield f"data: {json.dumps({'type': 'error', 'text': 'Please enter a question.'})}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    def event_stream():
        try:
            context, sources = build_context_and_sources(request.query, request.top_k)
        except Exception as e:
            print(f"[chat_stream] retrieval error: {e}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'text': f'Retrieval failed: {e}'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        if not sources:
            msg = "I couldn't find anything relevant in the TouchDesigner docs for that."
            yield f"data: {json.dumps({'type': 'delta', 'text': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Build the message list: system prompt (with fresh retrieval
        # context) + capped prior history + the new question. The prior
        # history is capped to avoid unbounded cost/latency growth as a
        # conversation gets long.
        capped_history = request.history[-MAX_HISTORY_MESSAGES:]
        messages = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(context=context)}]
        messages.extend({"role": m.role, "content": m.content} for m in capped_history)
        messages.append({"role": "user", "content": request.query})

        delta_count = 0
        try:
            stream = llm_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    delta_count += 1
                    yield f"data: {json.dumps({'type': 'delta', 'text': delta})}\n\n"

            if delta_count == 0:
                # Groq returned a stream with zero content deltas - surface
                # this clearly instead of silently finishing with no text.
                print("[chat_stream] Groq stream completed with zero content deltas")
                yield f"data: {json.dumps({'type': 'error', 'text': 'The model returned an empty response. Please try again.'})}\n\n"

        except Exception as e:
            print(f"[chat_stream] generation error: {e}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'text': f'Generation failed: {e}'})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

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
