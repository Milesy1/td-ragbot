# Stage 5: retrieve - semantic search against Qdrant (real stored
# vectors, not in-memory lists), plus hybrid retrieval via keyword
# search + Reciprocal Rank Fusion.
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py

from qdrant_client import QdrantClient

from embed import embed_text

COLLECTION_NAME = "touchdesigner_docs"

client = QdrantClient(url="http://localhost:6333")


def retrieve(query: str, top_k: int = 5) -> list:
    """
    Retrieve the top_k most relevant document chunks from Qdrant
    using semantic vector search.

    The query is embedded into a vector and compared against the
    stored document embeddings. The most similar chunks are returned.
    """

    if not query.strip():
        raise ValueError("query cannot be empty")

    try:
        query_vector = embed_text(query)

        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
        )

        return search_result.points

    except Exception as e:
        raise RuntimeError(f"Retrieval failed. Is Qdrant running? Error: {e}")


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
