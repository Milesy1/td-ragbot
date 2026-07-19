# embed.py — flow

```
embed_text("")
    ↓
ValueError
    ↓
stop early (no pointless API call)

embed_text("some document text")
    ↓
call Ollama (nomic-embed-text, via localhost:11434)
    ↓
success → return vector
    ↓
failure → RuntimeError with useful message
           ("Is Ollama running?")
```
