# Stage 4: ingest - walks a real folder of markdown docs, chunks by
# header, embeds via Ollama, and stores into Qdrant.
# Pipeline order: document.py -> chunk_text.py -> embed.py -> ingest.py -> retrieval.py

from pathlib import Path

from chunk_text import split_by_headers, chunk_section
from document import Document
from embed import embed_text
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


client = QdrantClient(url="http://localhost:6333")

if not client.collection_exists("touchdesigner_docs"):
    client.create_collection(
        collection_name="touchdesigner_docs",
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )


def ingest_folder(folder_path: str) -> None:
    """
    Ingest all supported documents from a folder into the vector database.

    For each file, read its contents, split it into sections and chunks,
    create a Document object for each chunk, generate embeddings, and
    store the results in the vector database.

    The document category is derived from the file's parent folder.
    """
    folder = Path(folder_path)
    # One running counter for the whole ingest run, so every chunk
    # across every file/section gets a unique Qdrant point id.
    point_id = 0

    for file_path in folder.rglob("*.md"):
        text = file_path.read_text(encoding="utf-8")
        doc_category = file_path.parent.name

        # split_by_headers returns (header_title, section_text) tuples -
        # unpack both directly in the loop
        sections = split_by_headers(text)

        for header_title, section_text in sections:
            # chunk_section needs chunk_size and overlap - not just text
            chunks = chunk_section(section_text, chunk_size=500, overlap=50)

            for chunk in chunks:
                document = Document(
                    content=chunk,
                    source=str(file_path),
                    header_title=header_title,
                    doc_category=doc_category
                )

                vector = embed_text(document.content)

                client.upsert(
                    collection_name="touchdesigner_docs",
                    points=[
                        PointStruct(
                            id=point_id,
                            vector=vector,
                            payload={
                                "content": document.content,
                                "source": document.source,
                                "header_title": document.header_title,
                                "doc_category": document.doc_category
                            }
                        )
                    ]
                )
                point_id += 1

    print(f"Ingested {point_id} chunks into 'touchdesigner_docs'")


if __name__ == "__main__":
    ingest_folder(r"E:\Projects\RagBot\TouchDesigner\docs_clean\wiki")
