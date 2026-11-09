from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"


def load_environment() -> None:
    # Deployment environment variables take precedence over local files.
    for path in (PROJECT_ROOT / ".env", APP_DIR / ".env", APP_DIR / "data" / ".env"):
        load_dotenv(path, override=False)


@dataclass(frozen=True)
class Settings:
    google_api_key: str = field(repr=False)
    chat_model: str = "gemini-3.5-flash-lite"
    embedding_model: str = "gemini-embedding-001"
    google_timeout: float = 30
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "sample_collection"
    qdrant_api_key: str | None = field(default=None, repr=False)
    qdrant_timeout: float = 10

    @classmethod
    def from_environment(cls) -> Settings:
        load_environment()
        settings = cls(
            google_api_key=(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip(),
            chat_model=os.getenv("GEMINI_CHAT_MODEL", "gemini-3.5-flash-lite").strip(),
            embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip(),
            google_timeout=float(os.getenv("GOOGLE_REQUEST_TIMEOUT", "30")),
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333").strip(),
            qdrant_collection=os.getenv("QDRANT_COLLECTION", "sample_collection").strip(),
            qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
            qdrant_timeout=float(os.getenv("QDRANT_TIMEOUT", "10")),
        )
        if settings.google_timeout <= 0 or settings.qdrant_timeout <= 0:
            raise ValueError("Service timeouts must be positive.")
        if not all((settings.chat_model, settings.embedding_model, settings.qdrant_url, settings.qdrant_collection)):
            raise ValueError("Model names and Qdrant settings must not be empty.")
        return settings

    def require_google_key(self) -> str:
        if not self.google_api_key:
            raise RuntimeError("Set GOOGLE_API_KEY in app/.env before using Gemini.")
        return self.google_api_key
