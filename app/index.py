from __future__ import annotations

import argparse
import hashlib
import math
from contextlib import closing
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from qdrant_client import QdrantClient, models

from app.config import APP_DIR, Settings
from app.services.clients import create_embeddings, create_qdrant_client


def load_pdf_documents(pdf_path: Path) -> list[Document]:
    reader = PdfReader(str(pdf_path))
    return [
        Document(page_content=text, metadata={"source": pdf_path.name, "page": page_number})
        for page_number, page in enumerate(reader.pages)
        if (text := (page.extract_text() or "").strip())
    ]


def _existing_chunk_indices(
    client: QdrantClient, collection: str, ids: list[str], chunks: list[Document], source_name: str
) -> set[int]:
    """Recognize both fingerprinted imports and older filename-based imports."""
    existing_ids = set()
    for start in range(0, len(ids), 64):
        existing_ids.update(
            str(point.id) for point in client.retrieve(
                collection, ids=ids[start:start + 64], with_payload=False, with_vectors=False
            )
        )
    known = {index for index, point_id in enumerate(ids) if point_id in existing_ids}
    if len(known) == len(chunks):
        return known

    # Initial versions did not record a source fingerprint. Compare their actual
    # source, page, and text so upgrading the indexer does not duplicate them.
    legacy_chunks = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection, limit=256, offset=offset, with_payload=True, with_vectors=False
        )
        for point in points:
            payload = point.payload or {}
            metadata = payload.get("metadata") or {}
            name = str(metadata.get("source", "")).replace("\\", "/").rsplit("/", 1)[-1]
            if not metadata.get("source_sha256") and name.casefold() == source_name.casefold():
                legacy_chunks.add((metadata.get("page"), payload.get("page_content")))
        if offset is None:
            break
    known.update(
        index for index, chunk in enumerate(chunks)
        if (chunk.metadata.get("page"), chunk.page_content) in legacy_chunks
    )
    return known


def index_pdf(settings: Settings, pdf_path: Path, *, append: bool = False) -> int:
    """Index one PDF; append mode adds missing chunks without replacing data."""
    with closing(create_qdrant_client(settings)) as client:
        exists = client.collection_exists(settings.qdrant_collection)
        if exists:
            existing_count = client.count(settings.qdrant_collection, exact=True).count
            if existing_count and not append:
                print(f"Knowledge base already contains {existing_count} chunks; no changes made.")
                return existing_count

        documents = load_pdf_documents(pdf_path)
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        ).split_documents(documents)
        if not chunks:
            raise ValueError("The PDF has no extractable text. Use a text-based PDF or run OCR first.")

        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        ids = [
            str(uuid5(NAMESPACE_URL, f"nuur-ai:pdf:{digest}:model:{settings.embedding_model}:chunk:{index}"))
            for index in range(len(chunks))
        ]
        known = _existing_chunk_indices(client, settings.qdrant_collection, ids, chunks, pdf_path.name) if exists else set()
        missing = [index for index in range(len(chunks)) if index not in known]
        if not missing:
            print(f"{pdf_path.name}: all {len(chunks)} chunks are already indexed; no changes made.")
            return 0

        embeddings = create_embeddings(settings)
        vectors = embeddings.embed_documents([chunks[index].page_content for index in missing])
        if len(vectors) != len(missing) or not vectors or not vectors[0]:
            raise ValueError("The embedding service returned incomplete vectors.")

        named_vectors = False
        dimensions = len(vectors[0])
        if exists:
            config = client.get_collection(settings.qdrant_collection).config.params.vectors
            if isinstance(config, dict):
                if "" not in config:
                    raise ValueError("The collection is missing the chatbot's default vector name.")
                config = config[""]
                named_vectors = True
            dimensions = config.size
        if any(len(vector) != dimensions or not all(math.isfinite(value) for value in vector) for vector in vectors):
            raise ValueError("Embeddings do not match the collection's vector dimensions.")

        if not exists:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE),
            )
        points = [
            models.PointStruct(
                id=ids[index],
                vector={"": vector} if named_vectors else vector,
                payload={
                    "page_content": chunks[index].page_content,
                    "metadata": {
                        **chunks[index].metadata,
                        "source": pdf_path.name,
                        "source_sha256": digest,
                        "embedding_model": settings.embedding_model,
                        "chunk_index": index,
                        "chunk_count": len(chunks),
                    },
                },
            )
            for index, vector in zip(missing, vectors, strict=True)
        ]
        for start in range(0, len(points), 64):
            client.upsert(settings.qdrant_collection, points=points[start:start + 64], wait=True)
        print(f"{pdf_path.name}: added {len(points)} chunks into {settings.qdrant_collection}.")
        return len(points)


def index_directory(settings: Settings, directory: Path) -> int:
    if not directory.is_dir():
        raise FileNotFoundError(f"PDF directory does not exist: {directory}")
    files = sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.casefold() == ".pdf"),
        key=lambda path: path.name.casefold(),
    )
    if not files:
        with closing(create_qdrant_client(settings)) as client:
            if client.collection_exists(settings.qdrant_collection) and client.count(settings.qdrant_collection, exact=True).count:
                print("No local PDFs supplied; existing knowledge collection is preserved.")
                return 0
        raise FileNotFoundError(f"Upload your private PDF files into {directory} before the first deployment.")
    added = sum(index_pdf(settings, pdf_path, append=True) for pdf_path in files)
    print(f"Processed {len(files)} PDFs; added {added} new chunks in total.")
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Index private PDFs into the configured Qdrant collection.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--pdf", type=Path, help="Index a single PDF (default: app/data/sample.pdf).")
    source.add_argument("--directory", type=Path, help="Add all PDFs in a directory, preserving existing chunks.")
    parser.add_argument("--append", action="store_true", help="Allow a single PDF to be added to an existing collection.")
    args = parser.parse_args()
    settings = Settings.from_environment()
    if args.directory:
        index_directory(settings, args.directory)
    else:
        index_pdf(settings, args.pdf or APP_DIR / "data" / "sample.pdf", append=args.append)


if __name__ == "__main__":
    main()
