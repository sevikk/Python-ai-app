import logging

from fastapi import APIRouter, HTTPException
from google.api_core.exceptions import GoogleAPIError

from app.core.config import get_gemini_api_key, get_gemini_model
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import generate_reply

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    api_key = get_gemini_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemini API is not configured. Set GEMINI_API_KEY in backend/.env.",
        )

    try:
        reply = generate_reply(
            message=request.message,
            api_key=api_key,
            model_name=get_gemini_model(),
        )
    except GoogleAPIError as error:
        logger.exception("Gemini API request failed")
        raise HTTPException(
            status_code=502,
            detail="Gemini API request failed. Check the backend logs.",
        ) from error

    return ChatResponse(reply=reply)
