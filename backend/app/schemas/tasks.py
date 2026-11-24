from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class TaskExtractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def require_non_whitespace_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text must contain at least one non-whitespace character.")
        return normalized


class ExtractedTask(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: Literal["low", "medium", "high"]
    due_date: Optional[date] = None


class TaskExtractionResponse(BaseModel):
    tasks: list[ExtractedTask] = Field(max_length=20)
