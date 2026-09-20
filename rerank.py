# Cross-encoder reranker over hybrid (RRF) candidates. MiniLM is small and
# local, same stack as the dense embedder. Scores replace RRF ranks for the
# list the LLM actually sees.
from functools import lru_cache

from config import HUGGINGFACE_TOKEN, RERANKER_MODEL


@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(RERANKER_MODEL, token=HUGGINGFACE_TOKEN)


def rerank(query: str, results: list, top_k: int) -> list[tuple[dict, float]]:
    """
    Re-score (payload, rrf_score) pairs with a cross-encoder.

    Returns (payload, ce_score) sorted highest-first, truncated to top_k.
    If the model cannot load, falls back to the incoming RRF order.
    """
    if not results:
        return []
    try:
        pairs = [
            (query, f"{payload.get('header_title') or ''}\n{payload.get('content') or ''}")
            for payload, _ in results
        ]
        scores = _reranker().predict(pairs)
        ranked = sorted(
            zip(results, scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [(payload, float(ce_score)) for (payload, _), ce_score in ranked[:top_k]]
    except Exception as e:
        print(f"[rerank] falling back to RRF order ({e})")
        return [(payload, float(score)) for payload, score in results[:top_k]]
