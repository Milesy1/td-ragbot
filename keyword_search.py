# Stage 6: keyword_search - lexical relevance scoring for hybrid retrieval.
# Uses Qdrant's text index on `content` to pre-filter candidates, then
# scores by keyword overlap. Falls back to a paginated full scroll if the
# text index has not been created yet (older collections).
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py -> keyword_search.py
from qdrant_client.http.models import Record
from qdrant_client.models import FieldCondition, Filter, MatchText

from config import (
    COLLECTION_NAME,
    KEYWORD_MAX_CANDIDATES,
    KEYWORD_SCROLL_PAGE,
    get_qdrant_client,
)


def keyword_score(query: str, content: str) -> int:
    """
    Calculate keyword overlap score between a query and document content.

    Returns the number of query keywords found in the content.
    """
    query_words = set(query.lower().split())
    content_words = set(content.lower().split())
    return len(query_words.intersection(content_words))


def _query_terms(query: str) -> list[str]:
    return [word for word in query.lower().split() if len(word) >= 2][:12]


def _text_filter(query: str) -> Filter | None:
    terms = _query_terms(query)
    if not terms:
        return None
    return Filter(
        should=[
            FieldCondition(key="content", match=MatchText(text=term))
            for term in terms
        ]
    )


def _scroll_points(scroll_filter: Filter | None, limit: int) -> list[Record]:
    client = get_qdrant_client()
    collected: list[Record] = []
    offset = None
    while len(collected) < limit:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=min(KEYWORD_SCROLL_PAGE, limit - len(collected)),
            offset=offset,
            scroll_filter=scroll_filter,
            with_payload=True,
        )
        if not points:
            break
        collected.extend(points)
        if offset is None:
            break
    return collected


def keyword_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the top_k most relevant document chunks using keyword matching.

    Candidates are pulled from Qdrant via a text-index filter (or a
    paginated scroll of up to KEYWORD_MAX_CANDIDATES points if the index
    is missing). Each chunk's content is scored against the query using
    keyword overlap. Zero-score hits are dropped so they cannot fill RRF.
    """
    if not query.strip():
        raise ValueError("query cannot be empty")

    try:
        text_filter = _text_filter(query)
        try:
            points = _scroll_points(text_filter, KEYWORD_MAX_CANDIDATES)
        except Exception as index_error:
            print(f"[keyword_search] text filter failed ({index_error}); falling back to full scroll")
            points = _scroll_points(None, KEYWORD_MAX_CANDIDATES)

        scored_results = []
        for point in points:
            payload = point.payload or {}
            content = payload.get("content") or ""
            score = keyword_score(query, content)
            if score <= 0:
                continue
            scored_results.append({"point": point, "score": score})

        scored_results.sort(key=lambda item: item["score"], reverse=True)
        return scored_results[:top_k]
    except Exception as e:
        raise RuntimeError(
            f"Keyword search failed. Is Qdrant running? Error: {e}"
        ) from e


if __name__ == "__main__":
    try:
        results = keyword_search("network editor nodes", top_k=3)
        for result in results:
            point = result["point"]
            print(f"Keyword score: {result['score']}")
            print(f"Header: {point.payload['header_title']}")
            print(f"Content: {point.payload['content'][:100]}...")
            print("-" * 40)
    except Exception as e:
        print(e)
