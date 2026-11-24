"""Pydantic schemas used to validate structured task extraction."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class TaskExtractionRequest(BaseModel):
    """Text submitted for extraction of explicitly stated actionable tasks."""

    text: str = Field(
        min_length=1,
        max_length=4000,
        description="Source text from which to identify actionable tasks.",
    )

    @field_validator("text")
    @classmethod
    def require_non_whitespace_text(cls, value: str) -> str:
        """Trim surrounding whitespace and reject content that is blank."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text must contain at least one non-whitespace character.")
        return normalized


class ExtractedTask(BaseModel):
    """One task extracted from the source text with constrained attributes."""

    title: str = Field(
        min_length=1,
        max_length=200,
        description="Short actionable task title grounded in the source text.",
    )
    priority: Literal["low", "medium", "high"] = Field(
        description="Urgency level explicitly supported by the source text.",
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Explicit task deadline as a date, or null when none is stated.",
    )


class TaskExtractionResponse(BaseModel):
    """Validated list of at most twenty extracted tasks."""

    tasks: list[ExtractedTask] = Field(
        max_length=20,
        description="Tasks found in the input; empty when none are actionable.",
    )
