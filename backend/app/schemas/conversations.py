from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessage]
