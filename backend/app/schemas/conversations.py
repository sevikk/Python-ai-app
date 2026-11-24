"""Pydantic response models for saved conversation history."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """A stored message returned as part of a conversation."""

    role: Literal["user", "assistant"] = Field(
        description="Identifies the author of the stored message.",
    )
    content: str = Field(description="Stored message text.")


class ConversationSummary(BaseModel):
    """Conversation metadata used in history lists."""

    id: str = Field(description="Stable identifier used to load or delete the chat.")
    title: str = Field(description="Display title derived from the first user message.")
    updated_at: datetime = Field(description="Time when the conversation last changed.")


class ConversationDetail(ConversationSummary):
    """Conversation summary plus its ordered message history."""

    messages: list[ConversationMessage] = Field(
        description="Messages ordered by their position in the conversation.",
    )
