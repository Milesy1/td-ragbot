# Stage 7: hybrid_search - combines semantic (retrieve) and keyword
# (keyword_search) results via Reciprocal Rank Fusion (RRF).
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py -> keyword_search.py -> hybrid_search.py
from concurrent.futures import ThreadPoolExecutor

from retrieval import retrieve
from keyword_search import keyword_search


def rrf_combine(semantic_results: list, keyword_results: list, k: int = 60) -> list:
    """
    Fuse a semantic ranking and a keyword ranking into one ranked list
    using Reciprocal Rank Fusion (RRF).

    Combines by RANK POSITION rather than raw score, since semantic
    scores (bounded cosine similarity) and keyword scores (unbounded
    overlap counts) are on incompatible scales. A chunk ranking well
    in both lists scores higher than one strong in only one.

    semantic_results: list of Qdrant point objects (from retrieve()),
        each with .id and .payload.
    keyword_results: list of dicts (from keyword_search()), each with
        "point" (a Qdrant point object) and "score".

    Returns a list of (payload, rrf_score) tuples, highest score first.
    """
    if not semantic_results and not keyword_results:
        return []

    # Accumulate RRF scores keyed by point id, since payloads themselves
    # aren't hashable and different result types (point vs dict) need
    # a common key to merge on.
    scores: dict = {}
    payloads: dict = {}

    for rank, point in enumerate(semantic_results):
        scores[point.id] = scores.get(point.id, 0) + 1 / (k + rank)
        payloads[point.id] = point.payload

    for rank, result in enumerate(keyword_results):
        point = result["point"]
        scores[point.id] = scores.get(point.id, 0) + 1 / (k + rank)
        payloads[point.id] = point.payload

    ranked_ids = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [(payloads[point_id], score) for point_id, score in ranked_ids]


def hybrid_search(query: str, top_k: int = 5) -> list:
    """
    Run semantic and keyword search in parallel, then fuse the results
    via RRF into a single ranked list of the top_k most relevant chunks.
    """
    if not query.strip():
        raise ValueError("query cannot be empty")

    with ThreadPoolExecutor(max_workers=2) as pool:
        semantic_future = pool.submit(retrieve, query, 20)
        keyword_future = pool.submit(keyword_search, query, 20)
        semantic_results = semantic_future.result()
        keyword_results = keyword_future.result()

    combined = rrf_combine(semantic_results, keyword_results)
    return combined[:top_k]


if __name__ == "__main__":
    try:
        results = hybrid_search("How do I use the network editor?", top_k=5)
        for payload, score in results:
            print(f"RRF score: {score:.4f}")
            print(f"Header: {payload['header_title']}")
            print(f"Content: {payload['content'][:100]}...")
            print("-" * 40)
    except Exception as e:
        print(e)
