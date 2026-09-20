# Stage 4: ingest - walks a real folder of markdown docs, chunks by
# header, embeds locally (all-MiniLM-L6-v2), stores dense + BM25 sparse
# vectors into Qdrant. Skips vendor/translation files. Tags each point
# with a corpus (wiki/book/github/interview) so query-time routing can
# keep github noise out of ordinary documentation questions.
import argparse
import os
import uuid
from pathlib import Path

from qdrant_client.models import (
    Distance,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    SparseVectorParams,
    TextIndexParams,
    TokenizerType,
    VectorParams,
)

from chunk_text import chunk_section, split_by_headers
from config import (
    COLLECTION_NAME,
    CORPUS_FROM_ROOT,
    DENSE_VECTOR_NAME,
    INGEST_BATCH_SIZE,
    SKIP_NAME_SUFFIXES,
    SKIP_PATH_PARTS,
    SPARSE_VECTOR_NAME,
    VECTOR_SIZE,
    get_qdrant_client,
)
from document import Document
from embed import embed_text
from lexical import sparse_tf


def stable_point_id(source: str, chunk_index: int) -> str:
    """Deterministic UUID from source path + chunk index (JSON-safe)."""
    key = f"{source}:{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def relative_source(file_path: Path, folder: Path) -> str:
    """Repo-relative posix path so IDs survive moving/renaming the drive."""
    folder = folder.resolve()
    file_path = file_path.resolve()
    root = folder.parent if folder.parent != folder else folder
    try:
        return file_path.relative_to(root).as_posix()
    except ValueError:
        try:
            return file_path.relative_to(folder).as_posix()
        except ValueError:
            return file_path.as_posix()


def corpus_for_source(source: str) -> str:
    root = source.split("/", 1)[0]
    return CORPUS_FROM_ROOT.get(root, "wiki")


def should_skip_file(file_path: Path) -> bool:
    name = file_path.name.lower()
    if name.endswith(SKIP_NAME_SUFFIXES):
        return True
    posix = f"/{file_path.as_posix().lower()}/"
    return any(part in posix for part in SKIP_PATH_PARTS)


def ensure_collection() -> None:
    """Create the named dense+sparse collection and payload indexes if missing."""
    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams(modifier=Modifier.IDF),
            },
        )

    indexes = [
        (
            "content",
            TextIndexParams(
                type="text",
                tokenizer=TokenizerType.WORD,
                min_token_len=2,
                lowercase=True,
            ),
        ),
        ("doc_category", PayloadSchemaType.KEYWORD),
        ("corpus", PayloadSchemaType.KEYWORD),
        ("source", PayloadSchemaType.KEYWORD),
        ("header_title", PayloadSchemaType.KEYWORD),
    ]
    for field_name, schema in indexes:
        try:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field_name,
                field_schema=schema,
            )
        except Exception as e:
            message = str(e).lower()
            if "already" not in message and "conflict" not in message:
                print(f"[ingest] payload index '{field_name}': {e}")


def _flush(points: list[PointStruct]) -> None:
    if not points:
        return
    get_qdrant_client().upsert(collection_name=COLLECTION_NAME, points=points)
    points.clear()


def ingest_folder(folder_path: str) -> None:
    """
    Ingest all supported documents from a folder into the vector database.

    Vendor trees (rapidjson, translations, VS project files) are skipped.
    Each point stores a dense MiniLM vector and a BM25 sparse vector.
    """
    ensure_collection()
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Ingest folder does not exist: {folder}")

    chunk_count = 0
    skipped_count = 0
    skipped_files = 0
    pending: list[PointStruct] = []

    for file_path in folder.rglob("*.md"):
        if should_skip_file(file_path):
            skipped_files += 1
            continue

        text = file_path.read_text(encoding="utf-8")
        doc_category = file_path.parent.name
        source = relative_source(file_path, folder)
        corpus = corpus_for_source(source)
        sections = split_by_headers(text)
        chunk_index = 0

        for header_title, section_text in sections:
            chunks = chunk_section(section_text, chunk_size=500, overlap=50)

            for chunk in chunks:
                if not chunk.strip():
                    skipped_count += 1
                    chunk_index += 1
                    continue

                document = Document(
                    content=chunk,
                    source=source,
                    header_title=header_title,
                    doc_category=doc_category,
                    corpus=corpus,
                )
                dense = embed_text(document.content)
                sparse = sparse_tf(f"{document.header_title}\n{document.content}")
                pending.append(
                    PointStruct(
                        id=stable_point_id(source, chunk_index),
                        vector={
                            DENSE_VECTOR_NAME: dense,
                            SPARSE_VECTOR_NAME: sparse,
                        },
                        payload={
                            "content": document.content,
                            "source": document.source,
                            "header_title": document.header_title,
                            "doc_category": document.doc_category,
                            "corpus": document.corpus,
                        },
                    )
                )
                chunk_index += 1
                chunk_count += 1

                if chunk_count % 25 == 0:
                    print(f"... {chunk_count} chunks ({file_path.name})", flush=True)

                if len(pending) >= INGEST_BATCH_SIZE:
                    _flush(pending)

    _flush(pending)
    print(
        f"Ingested {chunk_count} chunks into '{COLLECTION_NAME}' "
        f"({skipped_count} empty chunks skipped, {skipped_files} files skipped)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest markdown docs into Qdrant")
    parser.add_argument(
        "folder",
        nargs="?",
        default=os.environ.get("DOCS_FOLDER"),
        help="Folder of .md files (or set DOCS_FOLDER)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete the existing collection before ingesting (needed after schema changes)",
    )
    args = parser.parse_args()
    if not args.folder:
        raise SystemExit("Pass a folder path, e.g. python ingest.py path/to/docs_clean/wiki")
    if args.recreate:
        client = get_qdrant_client()
        if client.collection_exists(COLLECTION_NAME):
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted collection '{COLLECTION_NAME}'")
    ingest_folder(args.folder)
