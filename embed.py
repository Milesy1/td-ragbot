# Stage 3: embed - turns text into a 384-d vector using all-MiniLM-L6-v2.
# Prefers a local fastembed/ONNX model (fast, no per-chunk API, works
# offline). Falls back to Hugging Face Inference if the local model
# cannot be loaded (e.g. a slim deploy without torch).
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py
import time
from functools import lru_cache

from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError, OverloadedError

from config import EMBEDDING_MODEL, HUGGINGFACE_TOKEN, LOCAL_EMBEDDINGS

MAX_RETRIES = 4
BASE_DELAY_SECONDS = 2
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


@lru_cache(maxsize=1)
def _local_model():
    # ONNX port of the same model; vectors match sentence-transformers
    # (cosine 1.0), so the existing Qdrant index stays valid.
    from fastembed import TextEmbedding
    return TextEmbedding(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _hf_client() -> InferenceClient:
    return InferenceClient(provider="hf-inference", api_key=HUGGINGFACE_TOKEN)


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return int(status)
    response = getattr(exc, "response", None)
    if response is not None:
        return getattr(response, "status_code", None)
    return None


def _is_retryable(exc: Exception) -> bool:
    """Retry timeouts, overload, and transient HTTP errors — not 401/403/404."""
    if isinstance(exc, (TimeoutError, ConnectionError, InferenceTimeoutError, OverloadedError)):
        return True
    if isinstance(exc, HfHubHTTPError):
        status = _status_code(exc)
        return status in RETRYABLE_STATUS
    msg = str(exc).lower()
    return any(token in msg for token in ("timeout", "timed out", "429", "502", "503", "504", "overloaded"))


def _vector_from_result(result) -> list[float]:
    vector = result.mean(axis=0) if getattr(result, "ndim", 1) == 2 else result
    return vector.tolist() if hasattr(vector, "tolist") else list(vector)


def _embed_local(text: str) -> list[float]:
    vector = next(iter(_local_model().embed([text])))
    return _vector_from_result(vector)


def _embed_hf(text: str) -> list[float]:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            result = _hf_client().feature_extraction(text, model=EMBEDDING_MODEL)
            return _vector_from_result(result)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1 and _is_retryable(e):
                delay = BASE_DELAY_SECONDS * (2 ** attempt)
                print(f"[embed_text] HF attempt {attempt + 1} failed ({e}), retrying in {delay}s...")
                time.sleep(delay)
                continue
            break
    raise RuntimeError(
        f"Hugging Face embedding failed. Is HUGGINGFACE_TOKEN allowed to "
        f"call Inference Providers? Error: {last_error}"
    )


def embed_text(text: str) -> list[float]:
    """
    Generate a 384-dim vector embedding for the given text using
    all-MiniLM-L6-v2. Local sentence-transformers is tried first;
    Hugging Face's hosted Inference API is the fallback.
    """
    if not text.strip():
        raise ValueError("text cannot be empty")

    if not LOCAL_EMBEDDINGS:
        return _embed_hf(text)
    try:
        return _embed_local(text)
    except Exception as local_error:
        print(f"[embed_text] local model unavailable ({local_error}); falling back to HF Inference")
        return _embed_hf(text)


if __name__ == "__main__":
    vector = embed_text("TouchDesigner is a visual programming language.")
    print(f"Vector length: {len(vector)}")

    try:
        embed_text("")
    except ValueError as e:
        print(f"Correctly caught error: {e}")
