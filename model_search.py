# Side-quest: model_search - search Hugging Face's Hub programmatically
# to find and compare candidate embedding models, rather than always
# defaulting to all-MiniLM-L6-v2.
import os

from huggingface_hub import HfApi


def search_embedding_models(query: str = "sentence-similarity", limit: int = 10) -> list[dict]:
    """
    Search Hugging Face's Model Hub for candidate embedding models.

    Uses the HF_TOKEN environment variable if set (removes rate limits
    and "unauthenticated request" warnings) - falls back to anonymous
    access if not set, which still works but is slower/rate-limited.

    Returns a list of dicts with model id, downloads, and likes, sorted
    by download count (a rough proxy for "well-regarded / battle-tested").
    """
    if not query.strip():
        raise ValueError("query cannot be empty")

    token = os.environ.get("HUGGINGFACE_TOKEN")

    try:
        api = HfApi(token=token)
        # sort="downloads" is descending by default in current
        # huggingface_hub versions - no separate direction param needed.
        models = api.list_models(
            search=query,
            sort="downloads",
            limit=limit
        )
        return [
            {
                "id": m.id,
                "downloads": m.downloads,
                "likes": m.likes,
            }
            for m in models
        ]
    except Exception as e:
        raise RuntimeError(f"Hugging Face Hub search failed. Error: {e}")


if __name__ == "__main__":
    query = input("Search Hugging Face for: ")
    results = search_embedding_models(query, limit=10)
    for r in results:
        print(f"{r['id']:50s}  downloads={r['downloads']:>10}  likes={r['likes']}")

    try:
        search_embedding_models("")
    except ValueError as e:
        print(f"\nCorrectly caught error: {e}")
