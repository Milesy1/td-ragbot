# Stage 3: embed - turns text into a vector using Hugging Face's
# hosted Inference API (works both locally and when deployed - no
# local model server required, unlike the earlier Ollama version).
import os

from huggingface_hub import InferenceClient

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

client = InferenceClient(
    provider="hf-inference",
    api_key=os.environ.get("HUGGINGFACE_TOKEN"),
)


def embed_text(text: str) -> list[float]:
    """
    Generate a 384-dim vector embedding for the given text using
    Hugging Face's hosted Inference API (all-MiniLM-L6-v2).
    """
    if not text.strip():
        raise ValueError("text cannot be empty")

    try:
        result = client.feature_extraction(text, model=MODEL_NAME)
        # Some models return per-token vectors (2D array) - mean-pool
        # to a single sentence-level vector if so.
        vector = result.mean(axis=0) if result.ndim == 2 else result
        return vector.tolist()
    except Exception as e:
        raise RuntimeError(f"Embedding failed. Is HUGGINGFACE_TOKEN set correctly? Error: {e}")


if __name__ == "__main__":
    vector = embed_text("TouchDesigner is a visual programming language.")
    print(f"Vector length: {len(vector)}")

    try:
        embed_text("")
    except ValueError as e:
        print(f"Correctly caught error: {e}")
