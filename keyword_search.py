# Stage 6: keyword_search - BM25 sparse search (Qdrant IDF over hashed terms).
from qdrant_client.models import Filter

from config import COLLECTION_NAME, SPARSE_VECTOR_NAME, get_qdrant_client
from lexical import sparse_tf


def keyword_search(query: str, top_k: int = 5, query_filter: Filter | None = None) -> list[dict]:
    """
    Retrieve the top_k most relevant chunks using BM25 over the sparse
    `bm25` vector. Stopwords are stripped before the query is encoded.
    """
    if not query.strip():
        raise ValueError("query cannot be empty")

    try:
        search_result = get_qdrant_client().query_points(
            collection_name=COLLECTION_NAME,
            query=sparse_tf(query),
            using=SPARSE_VECTOR_NAME,
            query_filter=query_filter,
            limit=top_k,
        )
        return [
            {"point": point, "score": point.score}
            for point in search_result.points
            if point.score and point.score > 0
        ]
    except Exception as e:
        raise RuntimeError(
            f"Keyword search failed. Is Qdrant running? Error: {e}"
        ) from e


if __name__ == "__main__":
    try:
        results = keyword_search("network editor nodes", top_k=3)
        for result in results:
            point = result["point"]
            print(f"BM25 score: {result['score']}")
            print(f"Header: {point.payload['header_title']}")
            print(f"Content: {point.payload['content'][:100]}...")
            print("-" * 40)
    except Exception as e:
        print(e)
