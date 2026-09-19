# Stage 6: keyword_search - lexical relevance scoring for hybrid retrieval.
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py -> keyword_search.py
import os

from qdrant_client import QdrantClient

COLLECTION_NAME = "touchdesigner_docs"

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def keyword_score(query: str, content: str) -> int:
    """
    Calculate keyword overlap score between a query and document content.

    Returns the number of query keywords found in the content.
    """

    query_words = set(query.lower().split())
    content_words = set(content.lower().split())

    return len(query_words.intersection(content_words))


def keyword_search(query: str, top_k: int = 5) -> list:
    """
    Retrieve the top_k most relevant document chunks using keyword matching.

    Stored document chunks are pulled from Qdrant using scroll().
    Each chunk's content is scored against the query using keyword overlap.
    Results are returned in descending order of keyword relevance.
    """

    if not query.strip():
        raise ValueError("query cannot be empty")

    try:
        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
        )

        scored_results = []

        for point in points:
            content = point.payload["content"]

            score = keyword_score(query, content)

            scored_results.append(
                {
                    "point": point,
                    "score": score,
                }
            )

        scored_results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return scored_results[:top_k]

    except Exception as e:
        raise RuntimeError(
            f"Keyword search failed. Is Qdrant running? Error: {e}"
        )


if __name__ == "__main__":
    try:
        results = keyword_search(
            "network editor nodes",
            top_k=3
        )

        for result in results:
            point = result["point"]

            print(f"Keyword score: {result['score']}")
            print(f"Header: {point.payload['header_title']}")
            print(f"Content: {point.payload['content'][:100]}...")
            print("-" * 40)

    except Exception as e:
        print(e)
