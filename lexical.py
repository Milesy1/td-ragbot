# Lexical helpers for BM25 sparse vectors stored alongside dense embeddings.
# Term IDs are stable md5 prefixes (Python's hash() is process-randomized).
# Qdrant's Modifier.IDF applies collection-level IDF to the term frequencies
# we send, so this is real BM25 rather than naive word overlap.
import hashlib
import re
from collections import Counter

from qdrant_client.models import SparseVector

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do",
        "does", "for", "from", "had", "has", "have", "how", "i", "if", "in",
        "into", "is", "it", "its", "me", "my", "of", "on", "or", "our", "so",
        "than", "that", "the", "their", "then", "there", "these", "this",
        "to", "too", "up", "use", "used", "using", "was", "we", "what",
        "when", "where", "which", "who", "why", "will", "with", "you", "your",
    }
)


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, minus stopwords and 1-char noise."""
    tokens = TOKEN_RE.findall(text.lower())
    kept = [token for token in tokens if len(token) >= 2 and token not in STOPWORDS]
    return kept or [token for token in tokens if len(token) >= 2]


def term_id(term: str) -> int:
    digest = hashlib.md5(term.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31 - 1)


def sparse_tf(text: str) -> SparseVector:
    """Term-frequency sparse vector for Qdrant BM25 (IDF applied server-side)."""
    counts = Counter(tokenize(text))
    if not counts:
        return SparseVector(indices=[0], values=[1.0])
    by_id: dict[int, float] = {}
    for term, tf in counts.items():
        idx = term_id(term)
        by_id[idx] = by_id.get(idx, 0.0) + float(tf)
    indices = sorted(by_id)
    return SparseVector(indices=indices, values=[by_id[i] for i in indices])
