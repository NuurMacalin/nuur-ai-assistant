from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    """Check indexed storage without making paid calls to Google."""
    try:
        collection = request.app.state.qdrant_client.get_collection(
            request.app.state.settings.qdrant_collection
        )
        if not collection.points_count:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "knowledge_base": "empty"},
            )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "knowledge_base": "unavailable"},
        )
    return JSONResponse(content={
        "status": "ready",
        "knowledge_base": "indexed",
        "google": "configured; run python -m app.check_services --google to verify",
    })
