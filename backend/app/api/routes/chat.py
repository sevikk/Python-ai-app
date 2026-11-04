import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google.api_core.exceptions import GoogleAPIError

from app.core.config import get_gemini_api_key, get_gemini_model
from app.core.rate_limit import enforce_chat_rate_limit
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import generate_reply, stream_reply

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(enforce_chat_rate_limit)])


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
            messages=request.messages,
            api_key=api_key,
            model_name=get_gemini_model(),
        )
    except GoogleAPIError as error:
        logger.exception("Gemini API request failed")
        raise HTTPException(
            status_code=502,
            detail="Gemini API request failed. Check the backend logs.",
        ) from error
    except Exception as error:
        logger.exception("Unexpected error during Gemini request")
        raise HTTPException(
            status_code=502,
            detail="The response could not be generated. Check the backend logs.",
        ) from error

    return ChatResponse(reply=reply)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    api_key = get_gemini_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemini API is not configured. Set GEMINI_API_KEY in backend/.env.",
        )

    async def events() -> AsyncIterator[str]:
        try:
            async for token in stream_reply(
                messages=request.messages,
                api_key=api_key,
                model_name=get_gemini_model(),
            ):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield 'data: {"done":true}\n\n'
        except GoogleAPIError:
            logger.exception("Gemini streaming request failed")
            yield (
                "data: "
                + json.dumps(
                    {
                        "error": "Gemini API request failed. Check the backend logs."
                    }
                )
                + "\n\n"
            )
        except Exception:
            logger.exception("Unexpected error during Gemini streaming request")
            yield 'data: {"error":"The response stream failed. Check the backend logs."}\n\n'

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
