import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from google.api_core.exceptions import GoogleAPIError

from app.core.config import get_gemini_api_key, get_gemini_model
from app.core.rate_limit import enforce_chat_rate_limit
from app.db import database
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.tasks import TaskExtractionRequest, TaskExtractionResponse
from app.services.chat import extract_tasks, generate_reply, stream_reply
from app.services.conversations import (
    get_or_create_conversation,
    replace_conversation_messages,
)
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(enforce_chat_rate_limit)])


@router.post("/tasks/extract", response_model=TaskExtractionResponse)
def extract_tasks_from_text(request: TaskExtractionRequest) -> TaskExtractionResponse:
    api_key = get_gemini_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemini API is not configured. Set GEMINI_API_KEY in backend/.env.",
        )

    try:
        return extract_tasks(
            text=request.text,
            api_key=api_key,
            model_name=get_gemini_model(),
        )
    except GoogleAPIError as error:
        logger.exception("Gemini task extraction request failed")
        raise HTTPException(
            status_code=502,
            detail="Gemini API request failed. Check the backend logs.",
        ) from error
    except Exception as error:
        logger.exception("Could not extract structured tasks")
        raise HTTPException(
            status_code=502,
            detail="Tasks could not be extracted. Check the backend logs.",
        ) from error


@router.post("/chat", response_model=ChatResponse)
def chat(
    request_http: Request,
    request: ChatRequest,
    x_session_id: str = Header("anonymous", alias="X-Session-ID"),
) -> ChatResponse:
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

    conversation_id = request.conversation_id
    if database.SessionLocal is not None:
        db = database.SessionLocal()
        try:
            user = get_current_user(request_http, db)
            owner_id = user.id if user is not None else None
            conversation = get_or_create_conversation(
                db,
                x_session_id,
                conversation_id,
                owner_id,
            )
            from app.schemas.chat import ChatMessage

            saved_messages = list(request.messages) + [
                ChatMessage(role="assistant", content=reply)
            ]
            replace_conversation_messages(db, conversation, saved_messages)
            conversation_id = conversation.id
        except Exception:
            logger.exception("Could not persist chat response")
        finally:
            db.close()

    return ChatResponse(reply=reply)


@router.post("/chat/stream")
async def chat_stream(
    request_http: Request,
    request: ChatRequest,
    x_session_id: str = Header("anonymous", alias="X-Session-ID"),
) -> StreamingResponse:
    api_key = get_gemini_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemini API is not configured. Set GEMINI_API_KEY in backend/.env.",
        )

    async def events() -> AsyncIterator[str]:
        reply_parts: list[str] = []
        conversation_id = request.conversation_id
        try:
            async for token in stream_reply(
                messages=request.messages,
                api_key=api_key,
                model_name=get_gemini_model(),
            ):
                reply_parts.append(token)
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            if database.SessionLocal is not None:
                db = database.SessionLocal()
                try:
                    user = get_current_user(request_http, db)
                    owner_id = user.id if user is not None else None
                    conversation = get_or_create_conversation(
                        db,
                        x_session_id,
                        conversation_id,
                        owner_id,
                    )
                    from app.schemas.chat import ChatMessage

                    saved_messages = list(request.messages) + [
                        ChatMessage(
                            role="assistant",
                            content="".join(reply_parts),
                        )
                    ]
                    replace_conversation_messages(
                        db,
                        conversation,
                        saved_messages,
                    )
                    conversation_id = conversation.id
                except Exception:
                    logger.exception("Could not persist streaming chat response")
                    conversation_id = None
                finally:
                    db.close()
            else:
                conversation_id = None
            yield (
                "data: "
                + json.dumps(
                    {"done": True, "conversation_id": conversation_id},
                    ensure_ascii=False,
                )
                + "\n\n"
            )
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
