# document.py — flow

```
Document("", source, header_title, doc_category)
    ↓
ValueError
    ↓
stop early (no broken object created)

Document("real content", source, header_title, doc_category)
    ↓
content passes the check
    ↓
self.content, self.source, self.header_title,
self.doc_category all get set on the object
    ↓
success → a valid, fully-tagged Document instance
```
