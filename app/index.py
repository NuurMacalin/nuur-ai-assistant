from __future__ import annotations

import argparse
from contextlib import closing
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from qdrant_client import models

from app.config import APP_DIR, Settings
from app.services.clients import create_embeddings, create_qdrant_client


def load_pdf_documents(pdf_path: Path) -> list[Document]:
    reader = PdfReader(str(pdf_path))
    return [
        Document(page_content=text, metadata={"source": pdf_path.name, "page": page_number})
        for page_number, page in enumerate(reader.pages)
        if (text := (page.extract_text() or "").strip())
    ]


def index_pdf(settings: Settings, pdf_path: Path) -> int:
    """Create the configured collection once, preserving existing indexed data."""
    with closing(create_qdrant_client(settings)) as client:
        exists = client.collection_exists(settings.qdrant_collection)
        if exists:
            existing_count = client.count(settings.qdrant_collection, exact=True).count
            if existing_count:
                print(f"Knowledge base already contains {existing_count} chunks; no changes made.")
                return existing_count

        documents = load_pdf_documents(pdf_path)
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        ).split_documents(documents)
        if not chunks:
            raise ValueError("The PDF has no extractable text. Use a text-based PDF or run OCR first.")

        embeddings = create_embeddings(settings)
        vectors = embeddings.embed_documents([chunk.page_content for chunk in chunks])
        if len(vectors) != len(chunks) or not vectors or not vectors[0]:
            raise ValueError("The embedding service returned incomplete vectors.")

        if not exists:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE),
            )
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, f"nuur-ai:{pdf_path.name}:{index}")),
                vector=vector,
                payload={"page_content": document.page_content, "metadata": document.metadata},
            )
            for index, (document, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        for start in range(0, len(points), 64):
            client.upsert(settings.qdrant_collection, points=points[start:start + 64], wait=True)
        print(f"Indexed {len(points)} chunks into {settings.qdrant_collection}.")
        return len(points)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Nuur's PDF into the configured Qdrant collection.")
    parser.add_argument("--pdf", type=Path, default=APP_DIR / "data" / "sample.pdf")
    args = parser.parse_args()
    index_pdf(Settings.from_environment(), args.pdf)


if __name__ == "__main__":
    main()
