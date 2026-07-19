# Stage 2: chunk_text - splits raw markdown text into overlapping pieces.
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py
def split_by_headers(text: str) -> list[tuple[str, str]]:
    """Split a document into sections based on its Markdown headers."""
    current_header = None
    current_lines = []
    sections = []

    for line in text.splitlines():
        if line.startswith("#"):
            if current_header is not None:
                sections.append((current_header, "\n".join(current_lines)))

            current_header = line.strip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_header is not None:
        sections.append((current_header, "\n".join(current_lines)))

    return sections


def chunk_section(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split one section's text into overlapping character-count chunks.

    Used as a fallback for sections too long to be a single chunk.
    Overlap preserves meaning for content that sits on a chunk boundary.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size, or the loop never advances")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")

    start = 0
    chunks = []
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        # Step forward by less than a full chunk_size so the last
        # `overlap` characters repeat in the next chunk. Without this,
        # a sentence sitting on a boundary gets split and loses meaning.
        start = start + chunk_size - overlap
    return chunks


if __name__ == "__main__":
    sample = """# Introduction
This is the intro text.

## Getting Started
Here's how to get started.
More details here.

## Advanced Usage
Advanced stuff goes here."""

    result = split_by_headers(sample)
    for header, section_text in result:
        print(f"HEADER: {header}")
        print(f"TEXT: {section_text!r}")
        print()

    # Test chunk_section on a longer piece of text
    long_text = "abcdefghijklmnopqrstuvwxyz" * 3
    chunks = chunk_section(long_text, chunk_size=20, overlap=5)
    print(f"chunk_section produced {len(chunks)} chunks from {len(long_text)} chars")
    for c in chunks:
        print(repr(c))

    # Test error handling
    try:
        chunk_section("some text", chunk_size=10, overlap=10)
    except ValueError as e:
        print(f"Correctly caught error: {e}")
