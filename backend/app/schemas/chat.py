"""Pydantic models for chat requests, messages, and generated replies."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    """One validated user or assistant message in the submitted context."""

    role: Literal["user", "assistant"] = Field(
        description="Identifies whether the message came from the user or assistant.",
    )
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="Text content passed to or returned from the chat model.",
    )


class ChatRequest(BaseModel):
    """Conversation context and optional history ID sent to a chat endpoint."""

    messages: list[ChatMessage] = Field(
        min_length=1,
        max_length=20,
        description="Ordered context messages; the final message must be from the user.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Existing conversation to continue, or null to create one.",
    )

    @model_validator(mode="after")
    def require_latest_message_from_user(self) -> "ChatRequest":
        """Ensure the model request ends with a new user prompt."""
        if self.messages[-1].role != "user":
            raise ValueError("The latest message must be from the user.")
        return self


class ChatResponse(BaseModel):
    """Complete, non-streaming assistant response."""

    reply: str = Field(description="Generated assistant text.")
