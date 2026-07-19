# Stage 1: Document class - the data container each chunk gets wrapped in.
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py

class Document:
    # A Document wraps one chunk of text with the metadata needed to
    # trace it back to where it came from — required later for
    # citations and reranking. __init__ doesn't create the object;
    # it configures one that already exists.
    def __init__(self, content: str, source: str, header_title: str, doc_category: str):
        """Wraps one chunk of text with metadata for tracing it back to its source."""
        if not content:
            raise ValueError("content cannot be empty")
        self.content = content
        self.source = source
        self.header_title = header_title
        self.doc_category = doc_category


if __name__ == "__main__":
    d = Document("hello", "test.md", "Introduction", "document")
    print(d.content, d.source, d.header_title, d.doc_category)
    
    try:
        bad = Document("", "test.md", "Introduction", "document")
    except ValueError as e:
        print(f"Correctly caught error: {e}")
