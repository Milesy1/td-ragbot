# Stage 2: chunk_text - splits raw markdown text into overlapping pieces.
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py
import re

# CommonMark ATX headers require a space after the hashes. Matching any
# line that merely starts with "#" would treat Python comments and
# hashtags inside prose as section breaks.
HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def split_by_headers(text: str) -> list[tuple[str, str]]:
    """Split a document into sections based on its Markdown headers.

    Text before the first header is kept as a "Preamble" section.
    Lines inside fenced code blocks are never treated as headers, so a
    `# comment` in a Python example does not start a new section.
    """
    current_header = "Preamble"
    current_lines: list[str] = []
    sections: list[tuple[str, str]] = []
    in_fence = False

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if not body:
            return
        sections.append((current_header, body))

    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            current_lines.append(line)
            continue

        header_match = None if in_fence else HEADER_RE.match(line)
        if header_match:
            flush()
            current_header = header_match.group(2).strip() or current_header
            current_lines = []
        else:
            current_lines.append(line)

    flush()
    return sections


def chunk_section(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split one section's text into overlapping chunks.

    Used as a fallback for sections too long to be a single chunk.
    Overlap preserves meaning for content that sits on a chunk boundary.
    Breaks on whitespace when possible so words are not split in half.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size, or the loop never advances")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    text = text.strip()
    if not text:
        return []

    start = 0
    chunks: list[str] = []
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            split_at = text.rfind(" ", start, end)
            if split_at > start:
                end = split_at

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end
        # Overlap is a character count; snap back to a word boundary so
        # the next chunk does not start on "arlie" after "...charlie".
        if 0 < next_start < n and not text[next_start].isspace():
            snapped = text.rfind(" ", start, next_start)
            if snapped > start:
                next_start = snapped
        while next_start < n and text[next_start].isspace():
            next_start += 1
        if next_start <= start:
            next_start = end
            while next_start < n and text[next_start].isspace():
                next_start += 1
        start = next_start

    return chunks


if __name__ == "__main__":
    sample = """Leading prose kept as preamble.

# Introduction
This is the intro text.

```python
# this is a comment, not a header
print("hi")
```

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

    long_text = "abcdefghijklmnopqrstuvwxyz" * 3
    chunks = chunk_section(long_text, chunk_size=20, overlap=5)
    print(f"chunk_section produced {len(chunks)} chunks from {len(long_text)} chars")
    for c in chunks:
        print(repr(c))

    words = "alpha bravo charlie delta echo foxtrot golf hotel"
    print("whitespace chunks:", chunk_section(words, chunk_size=20, overlap=5))

    try:
        chunk_section("some text", chunk_size=10, overlap=10)
    except ValueError as e:
        print(f"Correctly caught error: {e}")
