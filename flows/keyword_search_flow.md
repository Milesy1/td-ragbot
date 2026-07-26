# keyword_search.py — flow

```
keyword_search("")
    ↓
ValueError (query cannot be empty)
    ↓
stop early

keyword_search("network editor nodes", top_k=3)
    ↓
client.scroll(collection, limit=100)
    → pulls back stored points directly, NO vector comparison -
      just "give me points" (returns a tuple: (points, next_offset))
    ↓
for each point:
    keyword_score(query, point.payload["content"])
        → lowercase + split both into word sets
        → count the overlap (set intersection)
    ↓
sort all scored points, highest overlap first
    ↓
return top_k
    ↓
failure (Qdrant down) → RuntimeError with useful message
```

Note: this is the LEXICAL half of hybrid retrieval only. It never touches
embeddings - retrieve() in retrieval.py handles the semantic half. The two
get combined via RRF as a separate step.
