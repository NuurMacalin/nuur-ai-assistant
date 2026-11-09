"""Deployment checks. Google checks send synthetic text only, never PDF excerpts."""
from __future__ import annotations

import argparse
from contextlib import closing

from app.config import Settings
from app.routes.chat import _is_google_authentication_error
from app.services.clients import create_chat_model, create_embeddings, create_qdrant_client


def check_services(settings: Settings, check_google: bool = False) -> bool:
    success = True
    try:
        with closing(create_qdrant_client(settings)) as client:
            collection = client.get_collection(settings.qdrant_collection)
            count = collection.points_count or 0
            if count:
                print(f"OK: Qdrant is reachable; {count} knowledge chunks are indexed.")
            else:
                print("FAIL: The knowledge collection is empty. Run python -m app.index.")
                success = False
    except Exception:
        print("FAIL: Qdrant or its collection is unavailable. Check QDRANT_URL and run python -m app.index.")
        success = False

    if not check_google:
        print("Google authentication was not checked. Add --google to send a synthetic connectivity test.")
        return success
    if not settings.google_api_key:
        print("FAIL: Set GOOGLE_API_KEY in app/.env or the server environment.")
        return False

    vector = None
    for stage, operation in (
        ("Gemini embeddings", lambda: create_embeddings(settings).embed_query("Service connectivity test")),
        ("Gemini chat", lambda: create_chat_model(settings).invoke("Reply only OK. This is a connectivity test.")),
    ):
        try:
            result = operation()
            if stage == "Gemini embeddings":
                vector = result
            elif not result.content:
                raise ValueError("Empty model response")
            print(f"OK: {stage} accepted the configured key and model.")
        except Exception as error:
            if _is_google_authentication_error(error):
                print(f"FAIL: {stage}: Google rejected the configured API key. Replace GOOGLE_API_KEY and restart the app.")
            else:
                print(f"FAIL: {stage} ({type(error).__name__}). Check model access, quota, and connectivity.")
            success = False

    if vector:
        try:
            with closing(create_qdrant_client(settings)) as client:
                client.query_points(
                    collection_name=settings.qdrant_collection,
                    query=vector,
                    limit=1,
                    with_payload=False,
                )
            print("OK: Query embeddings match the stored vector configuration.")
        except Exception:
            print("FAIL: The query embedding cannot search the stored collection. Check embedding model and vector dimensions.")
            success = False
    return success


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--google", action="store_true", help="Also make synthetic Google API checks.")
    args = parser.parse_args()
    raise SystemExit(0 if check_services(Settings.from_environment(), args.google) else 1)


if __name__ == "__main__":
    main()
