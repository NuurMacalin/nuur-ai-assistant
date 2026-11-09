import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from google.genai.errors import ClientError
from langchain_core.exceptions import ModelAuthenticationError

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.query import query_user


router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


def _is_google_authentication_error(error: Exception) -> bool:
    """Embedding errors wrap the provider exception; chat errors may be typed."""
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ModelAuthenticationError):
            return True
        if isinstance(current, ClientError) and (
            current.code == 401
            or (current.code == 400 and "API_KEY_INVALID" in str(current))
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    session_id = request.session_id or str(uuid4())
    try:
        answer = query_user(
            question=request.message,
            vector_store=http_request.app.state.vector_store,
            chat_model=http_request.app.state.chat_model,
        )
    except Exception as exc:
        if _is_google_authentication_error(exc):
            logger.error(
                "Gemini authentication failed. Update GOOGLE_API_KEY in app/.env "
                "with a working Google AI Studio key and restart FastAPI."
            )
            raise HTTPException(
                status_code=503,
                detail="The AI service could not authenticate. Please contact the site owner.",
            ) from exc
        logger.exception("Chat query failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The knowledge service is temporarily unavailable.",
        ) from exc
    return ChatResponse(answer=answer, session_id=session_id)
