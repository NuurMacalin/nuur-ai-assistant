from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from langchain_qdrant import QdrantVectorStore

from app.config import PROJECT_ROOT, Settings
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router
from app.services.clients import create_chat_model, create_embeddings, create_qdrant_client


FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_environment()
    settings.require_google_key()
    qdrant_client = create_qdrant_client(settings)
    try:
        app.state.settings = settings
        app.state.qdrant_client = qdrant_client
        embeddings = create_embeddings(settings)
        app.state.vector_store = QdrantVectorStore(
            client=qdrant_client,
            collection_name=settings.qdrant_collection,
            embedding=embeddings,
            vector_name="",
            validate_embeddings=False,
            validate_collection_config=False,
        )
        app.state.chat_model = create_chat_model(settings)
        yield
    finally:
        qdrant_client.close()


app = FastAPI(title="Nuur AI", version="1.0.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(chat_router)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
