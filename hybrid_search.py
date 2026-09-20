# Stage 7: hybrid_search - dense + BM25 in parallel, RRF fuse, then
# cross-encoder rerank. Github/interview corpora are excluded unless
# the query looks like it needs them.
from concurrent.futures import ThreadPoolExecutor

from qdrant_client.models import FieldCondition, Filter, MatchAny

from config import (
    DEFAULT_CORPORA,
    GITHUB_QUERY_HINTS,
    HYBRID_CANDIDATES,
    INTERVIEW_QUERY_HINTS,
)
from keyword_search import keyword_search
from rerank import rerank
from retrieval import retrieve


def corpora_for_query(query: str) -> list[str]:
    """Wiki + book by default; github/interview only when the query asks for them."""
    lowered = query.lower()
    corpora = list(DEFAULT_CORPORA)
    if any(hint in lowered for hint in GITHUB_QUERY_HINTS):
        corpora.append("github")
    if any(hint in lowered for hint in INTERVIEW_QUERY_HINTS):
        corpora.append("interview")
    return corpora


def corpus_filter(query: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key="corpus",
                match=MatchAny(any=corpora_for_query(query)),
            )
        ]
    )


def rrf_combine(semantic_results: list, keyword_results: list, k: int = 60) -> list:
    """
    Fuse a semantic ranking and a BM25 ranking into one ranked list
    using Reciprocal Rank Fusion (RRF). Returns (payload, rrf_score).
    """
    if not semantic_results and not keyword_results:
        return []

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
    Dense + BM25 in parallel (filtered by corpus), RRF fuse, then
    cross-encoder rerank to top_k. Each item is (payload, rerank_score).
    """
    if not query.strip():
        raise ValueError("query cannot be empty")

    query_filter = corpus_filter(query)
    with ThreadPoolExecutor(max_workers=2) as pool:
        semantic_future = pool.submit(retrieve, query, HYBRID_CANDIDATES, query_filter)
        keyword_future = pool.submit(keyword_search, query, HYBRID_CANDIDATES, query_filter)
        semantic_results = semantic_future.result()
        keyword_results = keyword_future.result()

    combined = rrf_combine(semantic_results, keyword_results)
    return rerank(query, combined, top_k=top_k)


if __name__ == "__main__":
    try:
        results = hybrid_search("How do I use the network editor?", top_k=5)
        for payload, score in results:
            print(f"Rerank score: {score:.4f}")
            print(f"Corpus: {payload.get('corpus')}")
            print(f"Header: {payload['header_title']}")
            print(f"Source: {payload.get('source')}")
            print(f"Content: {payload['content'][:100]}...")
            print("-" * 40)
    except Exception as e:
        print(e)
