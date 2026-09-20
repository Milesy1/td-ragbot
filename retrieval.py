# Stage 5: retrieve - dense semantic search against the named "dense" vector.
from qdrant_client.http.models import ScoredPoint
from qdrant_client.models import Filter

from config import COLLECTION_NAME, DENSE_VECTOR_NAME, get_qdrant_client
from embed import embed_text


def retrieve(query: str, top_k: int = 5, query_filter: Filter | None = None) -> list[ScoredPoint]:
    """
    Retrieve the top_k most relevant document chunks from Qdrant
    using semantic vector search on the dense MiniLM embeddings.
    """
    if not query.strip():
        raise ValueError("query cannot be empty")

    try:
        query_vector = embed_text(query)
        search_result = get_qdrant_client().query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            using=DENSE_VECTOR_NAME,
            query_filter=query_filter,
            limit=top_k,
        )
        return search_result.points
    except Exception as e:
        raise RuntimeError(f"Retrieval failed. Is Qdrant running? Error: {e}") from e


if __name__ == "__main__":
    try:
        results = retrieve("How do I use the network editor?", top_k=3)
        for point in results:
            print(f"Score: {point.score:.4f}")
            print(f"Header: {point.payload['header_title']}")
            print(f"Content: {point.payload['content'][:100]}...")
            print()
    except Exception as e:
        print(e)
