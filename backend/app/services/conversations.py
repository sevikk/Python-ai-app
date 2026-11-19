from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.schemas.chat import ChatMessage


def get_or_create_conversation(
    db: Session,
    session_id: str,
    conversation_id: Optional[str],
    owner_id: Optional[str] = None,
) -> Conversation:
    if conversation_id:
        conversation = db.get(Conversation, conversation_id)
        if conversation and (
            (owner_id is not None and conversation.owner_id == owner_id)
            or (owner_id is None and conversation.owner_id is None
                and conversation.session_id == session_id)
        ):
            return conversation

    conversation = Conversation(session_id=session_id, owner_id=owner_id)
    db.add(conversation)
    db.flush()
    return conversation


def list_conversations(
    db: Session,
    session_id: str,
    owner_id: Optional[str] = None,
) -> list[Conversation]:
    query = select(Conversation).order_by(Conversation.updated_at.desc())
    if owner_id is not None:
        query = query.where(Conversation.owner_id == owner_id)
    else:
        query = query.where(
            Conversation.owner_id.is_(None),
            Conversation.session_id == session_id,
        )
    result = db.scalars(query)
    return list(result)


def get_conversation(
    db: Session,
    session_id: str,
    conversation_id: str,
    owner_id: Optional[str] = None,
) -> Optional[Conversation]:
    conversation = db.get(Conversation, conversation_id)
    if conversation and (
        (owner_id is not None and conversation.owner_id == owner_id)
        or (owner_id is None and conversation.owner_id is None
            and conversation.session_id == session_id)
    ):
        return conversation
    return None


def delete_conversation(
    db: Session,
    session_id: str,
    conversation_id: str,
    owner_id: Optional[str] = None,
) -> bool:
    conversation = get_conversation(
        db,
        session_id,
        conversation_id,
        owner_id,
    )
    if conversation is None:
        return False
    db.delete(conversation)
    db.commit()
    return True


def delete_empty_conversations(db: Session) -> int:
    conversations = list(
        db.scalars(
            select(Conversation).where(~Conversation.messages.any())
        )
    )
    for conversation in conversations:
        db.delete(conversation)
    db.commit()
    return len(conversations)


def claim_anonymous_conversations(
    db: Session,
    session_id: str,
    owner_id: str,
) -> int:
    conversations = list(
        db.scalars(
            select(Conversation).where(
                Conversation.owner_id.is_(None),
                Conversation.session_id == session_id,
            )
        )
    )
    for conversation in conversations:
        conversation.owner_id = owner_id
    db.commit()
    return len(conversations)


def replace_conversation_messages(
    db: Session,
    conversation: Conversation,
    messages: list[ChatMessage],
) -> None:
    for message in list(conversation.messages):
        db.delete(message)
    db.flush()

    for position, message in enumerate(messages):
        db.add(
            Message(
                conversation_id=conversation.id,
                role=message.role,
                content=message.content,
                position=position,
            )
        )

    if messages:
        first_user = next(
            (message.content for message in messages if message.role == "user"),
            "New chat",
        )
        conversation.title = first_user[:200]
    db.commit()
