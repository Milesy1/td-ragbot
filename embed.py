# Stage 3: embed - turns text into a vector using Hugging Face's
# hosted Inference API (works both locally and when deployed - no
# local model server required, unlike the earlier Ollama version).
# Retries transient failures (HF's serverless inference occasionally
# returns 502/503 under load or while a model "wakes up") with
# exponential backoff, since a single hiccup shouldn't kill a long
# ingestion run over thousands of chunks.
import os
import time

from huggingface_hub import InferenceClient

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MAX_RETRIES = 4
BASE_DELAY_SECONDS = 2

client = InferenceClient(
    provider="hf-inference",
    api_key=os.environ.get("HUGGINGFACE_TOKEN"),
)


def embed_text(text: str) -> list[float]:
    """
    Generate a 384-dim vector embedding for the given text using
    Hugging Face's hosted Inference API (all-MiniLM-L6-v2).

    Retries transient server errors (502/503/timeouts) with exponential
    backoff (2s, 4s, 8s, 16s) before giving up, since these are common
    and usually resolve within a few seconds.
    """
    if not text.strip():
        raise ValueError("text cannot be empty")

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            result = client.feature_extraction(text, model=MODEL_NAME)
            # Some models return per-token vectors (2D array) - mean-pool
            # to a single sentence-level vector if so.
            vector = result.mean(axis=0) if result.ndim == 2 else result
            return vector.tolist()
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY_SECONDS * (2 ** attempt)
                print(f"[embed_text] attempt {attempt + 1} failed ({e}), retrying in {delay}s...")
                time.sleep(delay)

    raise RuntimeError(f"Embedding failed after {MAX_RETRIES} attempts. Is HUGGINGFACE_TOKEN set correctly? Error: {last_error}")


if __name__ == "__main__":
    vector = embed_text("TouchDesigner is a visual programming language.")
    print(f"Vector length: {len(vector)}")

    try:
        embed_text("")
    except ValueError as e:
        print(f"Correctly caught error: {e}")
