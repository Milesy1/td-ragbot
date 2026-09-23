# Cross-encoder reranker over hybrid (RRF) candidates. MiniLM is small and
# local, same stack as the dense embedder. Scores replace RRF ranks for the
# list the LLM actually sees.
from functools import lru_cache

from config import ONNX_THREADS, RERANK_CANDIDATES, RERANK_ENABLED, RERANKER_MODEL


@lru_cache(maxsize=1)
def _reranker():
    # fastembed ONNX port; raw logits match the sentence-transformers
    # CrossEncoder, so WEAK_RERANK_THRESHOLD keeps its meaning.
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    return TextCrossEncoder(RERANKER_MODEL, threads=ONNX_THREADS)


def rerank(query: str, results: list, top_k: int) -> list[tuple[dict, float]]:
    """
    Re-score (payload, rrf_score) pairs with a cross-encoder.

    Returns (payload, ce_score) sorted highest-first, truncated to top_k.
    If the model cannot load, falls back to the incoming RRF order.
    """
    if not results:
        return []
    if not RERANK_ENABLED:
        return [(payload, float(score)) for payload, score in results[:top_k]]
    results = results[:RERANK_CANDIDATES]
    try:
        documents = [
            f"{payload.get('header_title') or ''}\n{payload.get('content') or ''}"
            for payload, _ in results
        ]
        # ONNX Runtime's arena keeps the peak batch allocation for the life
        # of the process; batch_size=1 keeps that peak ~1/20th the default.
        scores = list(_reranker().rerank(query, documents, batch_size=1))
        ranked = sorted(
            zip(results, scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [(payload, float(ce_score)) for (payload, _), ce_score in ranked[:top_k]]
    except Exception as e:
        print(f"[rerank] falling back to RRF order ({e})")
        return [(payload, float(score)) for payload, score in results[:top_k]]
