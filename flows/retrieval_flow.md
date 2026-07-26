# retrieval.py — flow (semantic retrieval)

```
retrieve("")
    ↓
ValueError (query cannot be empty)
    ↓
stop early

retrieve("How do I use the network editor?", top_k=3)
    ↓
embed_text(query) → 768-dim query vector
    ↓
client.query_points(collection, query=vector, limit=top_k)
    ↓
success → return the top_k scored points
           (each has .score, .payload with content/source/
           header_title/doc_category)
    ↓
failure (Qdrant down, bad collection name, etc.)
    → RuntimeError with useful message
      ("Is Qdrant running?")
```

Note: uses `client.query_points()`, not the deprecated `client.search()`.
`query_points` takes the vector via `query=`, not `query_vector=`, and
returns a response object - the actual points are in `.points`, not the
response itself.
