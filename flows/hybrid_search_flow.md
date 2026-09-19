# hybrid_search.py — flow

```
rrf_combine([], [])
    ↓
ValueError (both inputs empty)

rrf_combine(semantic_results, keyword_results, k=60)
    ↓
for rank, point in semantic_results:
    scores[point.id] += 1 / (k + rank)
for rank, result in keyword_results:
    scores[point.id] += 1 / (k + rank)
    ↓
(a chunk in BOTH lists accumulates BOTH contributions -
 scores keyed by point.id since payloads aren't hashable)
    ↓
sort by combined score, descending
    ↓
return [(payload, score), ...]

hybrid_search("")
    ↓
ValueError (query cannot be empty)

hybrid_search("How do I use the network editor?", top_k=5)
    ↓
retrieve(query, top_k=20)     -> semantic results (Qdrant vector search)
keyword_search(query, top_k=20) -> lexical results (Qdrant scroll + overlap)
    ↓
rrf_combine(semantic, keyword)
    ↓
return top_k fused results
```
