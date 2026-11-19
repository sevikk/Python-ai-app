from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Conversation
from app.schemas.conversations import (
    ConversationDetail,
    ConversationMessage,
    ConversationSummary,
)
from app.services.conversations import (
    delete_conversation,
    get_conversation,
    list_conversations,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_session_id(x_session_id: str = Header(..., alias="X-Session-ID")) -> str:
    if not x_session_id.strip():
        raise HTTPException(status_code=400, detail="X-Session-ID is required.")
    return x_session_id.strip()


@router.get("", response_model=list[ConversationSummary])
def list_user_conversations(
    request: Request,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_db),
) -> list[ConversationSummary]:
    user = get_current_user(request, db)
    owner_id = user.id if user is not None else None
    conversations = list_conversations(db, session_id, owner_id)
    return [
        ConversationSummary(
            id=conversation.id,
            title=conversation.title,
            updated_at=conversation.updated_at,
        )
        for conversation in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_user_conversation(
    conversation_id: str,
    request: Request,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    user = get_current_user(request, db)
    owner_id = user.id if user is not None else None
    conversation = get_conversation(
        db,
        session_id,
        conversation_id,
        owner_id,
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return _conversation_detail(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_conversation(
    conversation_id: str,
    request: Request,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_db),
) -> None:
    user = get_current_user(request, db)
    owner_id = user.id if user is not None else None
    if not delete_conversation(db, session_id, conversation_id, owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )


def _conversation_detail(conversation: Conversation) -> ConversationDetail:
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        updated_at=conversation.updated_at,
        messages=[
            ConversationMessage(role=message.role, content=message.content)
            for message in conversation.messages
        ],
    )
