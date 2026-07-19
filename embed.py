# Stage 3: embed - turns text into a vector using local Ollama (nomic-embed-text).
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # required by the library, but Ollama ignores it
)

def embed_text(text: str) -> list[float]:
    """Generate a vector embedding for the given text using Ollama's nomic-embed-text model."""

    if not text.strip():
        raise ValueError("text cannot be empty")

    try:
        response = client.embeddings.create(
            model="nomic-embed-text",
            input=text
        )
        return response.data[0].embedding

    except Exception as e:
        raise RuntimeError(f"Embedding failed. Is Ollama running? Error: {e}")
    
if __name__ == "__main__":
    vector = embed_text("TouchDesigner is a visual programming language.")
    print(f"Vector length: {len(vector)}")

    try:
        embed_text("")
    except ValueError as e:
        print(f"Correctly caught error: {e}")