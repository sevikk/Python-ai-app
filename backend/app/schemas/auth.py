"""Pydantic request and response models for account authentication."""

from pydantic import BaseModel, EmailStr, Field


class AuthRequest(BaseModel):
    """Credentials submitted for registration or login."""

    email: EmailStr = Field(description="Account email address, normalized by the API.")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Account password; accepted only in the authentication request.",
    )


class UserResponse(BaseModel):
    """Public account details returned after successful authentication."""

    id: str = Field(description="Stable identifier of the authenticated account.")
    email: str = Field(description="Normalized email address of the account.")
