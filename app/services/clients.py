from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from qdrant_client import QdrantClient

from app.config import Settings


def create_qdrant_client(settings: Settings) -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout,
    )


def create_embeddings(settings: Settings) -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=settings.require_google_key(),
        client_args={"timeout": settings.google_timeout},
    )


def create_chat_model(settings: Settings) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.chat_model,
        api_key=settings.require_google_key(),
        max_tokens=700,
        request_timeout=settings.google_timeout,
        retries=1,
    )
