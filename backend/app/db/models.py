"""SQLAlchemy models for chat conversations and their ordered messages."""

from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Conversation(Base):
    """A chat thread owned by an anonymous session or registered user."""

    __tablename__ = "conversations"

    # Stable public identifier for routes and conversation references.
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID identifying this conversation.",
    )
    # Browser session identifier used to isolate conversations before login.
    session_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        comment="Anonymous browser session that created the conversation.",
    )
    # Optional account owner; null means the conversation remains anonymous.
    owner_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_conversations_owner_id_users",
        ),
        nullable=True,
        index=True,
        comment="Registered user who owns this conversation, when claimed.",
    )
    # Preview title derived from the first user message.
    title: Mapped[str] = mapped_column(
        String(200),
        default="New chat",
        comment="Short display title derived from the conversation's first user message.",
    )
    # Creation timestamp used for history display and auditing.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Time when the conversation was created.",
    )
    # Updated whenever saved conversation data changes.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Time when the conversation was last updated.",
    )
    # Ordered child messages; deleting the parent also deletes its messages.
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.position",
    )


class Message(Base):
    """One user or assistant entry stored in a conversation's history."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "position", name="uq_message_position"),
    )

    # Stable identifier for this persisted message.
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID identifying this message.",
    )
    # Parent conversation; database cascade removes messages with the parent.
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        comment="Conversation that contains this message.",
    )
    # Role determines how the message is presented and passed to the model.
    role: Mapped[Literal["user", "assistant"]] = mapped_column(
        String(9),
        comment="Whether the message was written by the user or assistant.",
    )
    # Full text content sent or returned in the chat.
    content: Mapped[str] = mapped_column(
        Text,
        comment="Text content of this message.",
    )
    # Zero-based order within the conversation, unique per parent thread.
    position: Mapped[int] = mapped_column(
        comment="Zero-based position used to restore conversation order.",
    )
    # Creation timestamp used for message history and auditing.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Time when the message was stored.",
    )
    # ORM back-reference lets conversation code access the parent thread.
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
