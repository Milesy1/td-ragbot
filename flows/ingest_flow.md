# ingest.py — flow

```
ingest_folder("path/to/docs_clean/wiki")
    ↓
walk every *.md file recursively (Path.rglob)
    ↓
for each file:
    read the text
    doc_category = parent folder name (e.g. "wiki")
    ↓
    split_by_headers(text)
        → [(header_title, section_text), ...]
    ↓
    for each (header_title, section_text):
        chunk_section(section_text, chunk_size, overlap)
            → [chunk, chunk, chunk, ...]
        ↓
        for each chunk:
            wrap in Document(content, source, header_title, doc_category)
            ↓
            embed_text(document.content) → 768-dim vector
            ↓
            client.upsert(collection, PointStruct(id, vector, payload))
            (payload = content + source + header_title + doc_category)
            ↓
            point_id += 1  (one running counter across the WHOLE run)
    ↓
print total chunks ingested
```

Collection creation is guarded: `if not client.collection_exists(...)` before
`create_collection` - re-running ingest_folder never tries to recreate an
already-existing collection.
