# Shared runtime config. Every other module imports from here so Qdrant
# URL/collection name/embedding model cannot drift between ingest and query.
import os
from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient


def _load_dotenv() -> None:
    """Load .env into os.environ without overriding values already set
    (so Render/production env vars always win)."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

COLLECTION_NAME = "touchdesigner_docs"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimension
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# ASCII-only label (no Unicode middle-dot) - avoids encoding mismatches
# between this file's saved encoding and Render's runtime.
EMBEDDING_MODEL_LABEL = "all-MiniLM-L6-v2 (384d) + MiniLM reranker"

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

HUGGINGFACE_TOKEN = os.environ.get("HUGGINGFACE_TOKEN")
if HUGGINGFACE_TOKEN:
    os.environ.setdefault("HF_TOKEN", HUGGINGFACE_TOKEN)

MAX_HISTORY_MESSAGES = 10
MAX_HISTORY_ITEMS = 20
MAX_QUERY_LENGTH = 4000
MAX_MESSAGE_CONTENT_LENGTH = 8000
MIN_TOP_K = 1
MAX_TOP_K = 20
DEFAULT_TOP_K = 5
HYBRID_CANDIDATES = 20

INGEST_BATCH_SIZE = 64

# Default retrieval stays on official/docs-like corpora. Github and the
# interview are opted in only when the query looks like it needs them.
DEFAULT_CORPORA = ("wiki", "book")
GITHUB_QUERY_HINTS = (
    "github",
    "plugin",
    "c++",
    "cplusplus",
    "unreal",
    "touchengine",
    "touch engine",
    "ue5",
    "ue4",
    "dll",
    "sdk",
    "cmake",
)
INTERVIEW_QUERY_HINTS = ("pauric", "generative hut", "generativehut", "interview")

# Cross-encoder scores below this are treated as weakly related context.
WEAK_RERANK_THRESHOLD = 0.0

CORPUS_FROM_ROOT = {
    "wiki": "wiki",
    "wiki_full": "wiki",
    "introduction-book": "book",
    "github_repos": "github",
    "pauric_freeman": "interview",
    "forum": "forum",
}

SKIP_NAME_SUFFIXES = (".zh-cn.md", ".zh.md", ".ja.md", ".ko.md")
SKIP_PATH_PARTS = (
    "/rapidjson",
    "/node_modules/",
    "/.git/",
    "/vs/",
    "/third_party/",
    "/third-party/",
    "/vendor/",
)


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Lazy singleton so importing a module does not require Qdrant to be up."""
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
