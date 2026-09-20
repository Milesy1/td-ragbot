# Stage 4: ingest - walks a real folder of markdown docs, chunks by
# header, embeds via Hugging Face Inference API, and stores into
# Qdrant Cloud (falls back to local Qdrant if no cloud URL is set).
# Uses stable, deterministic UUID point IDs (uuid5 of source path + chunk
# index) rather than a per-run counter or a 64-bit int packed through JSON
# (integers above 2^53 lose precision over HTTP). Re-running the same folder
# updates existing points instead of duplicating them.
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py
import argparse
import os
import uuid
from pathlib import Path

from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    TextIndexParams,
    TokenizerType,
    VectorParams,
)

from chunk_text import chunk_section, split_by_headers
from config import (
    COLLECTION_NAME,
    INGEST_BATCH_SIZE,
    VECTOR_SIZE,
    get_qdrant_client,
)
from document import Document
from embed import embed_text


def stable_point_id(source: str, chunk_index: int) -> str:
    """
    Generate a deterministic UUID from a source path + chunk index,
    so the same chunk always maps to the same Qdrant point ID across
    runs. UUIDs are JSON-safe (unlike 64-bit ints, which lose precision
    above 2^53).
    """
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


def ensure_collection() -> None:
    """Create the collection and payload indexes if they are missing."""
    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
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

    For each file, read its contents, split it into sections and chunks,
    create a Document object for each chunk, generate embeddings, and
    store the results in the vector database (batched upserts).

    The document category is derived from the file's parent folder.
    Chunks that are empty or whitespace-only after chunking (e.g. a
    section that's just blank lines) are skipped rather than raising -
    embed_text() correctly rejects them, but one bad chunk shouldn't
    crash an otherwise-successful multi-hundred-chunk ingestion run.
    """
    ensure_collection()
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Ingest folder does not exist: {folder}")

    chunk_count = 0
    skipped_count = 0
    pending: list[PointStruct] = []

    for file_path in folder.rglob("*.md"):
        text = file_path.read_text(encoding="utf-8")
        doc_category = file_path.parent.name
        source = relative_source(file_path, folder)

        sections = split_by_headers(text)

        # chunk_index counts every chunk within THIS FILE (across all its
        # sections), so stable_point_id(source, chunk_index) is unique
        # per file regardless of how many sections/chunks it has.
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
                )
                vector = embed_text(document.content)
                pending.append(
                    PointStruct(
                        id=stable_point_id(source, chunk_index),
                        vector=vector,
                        payload={
                            "content": document.content,
                            "source": document.source,
                            "header_title": document.header_title,
                            "doc_category": document.doc_category,
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
        f"({skipped_count} empty chunks skipped)"
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
        help="Delete the existing collection before ingesting (needed after ID-scheme changes)",
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
