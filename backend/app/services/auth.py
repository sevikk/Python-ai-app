"""Signed-cookie authentication helpers used by account and chat routes."""

from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_session_secret
from app.db.auth_models import User

# Browser cookie name shared by cookie issuance, lookup, and logout handlers.
SESSION_COOKIE = "ai_chat_session"
# Authentication cookies remain valid for one week after they are issued.
SESSION_MAX_AGE = 60 * 60 * 24 * 7


def _serializer() -> URLSafeTimedSerializer:
    """Build the cookie signer using the validated configured secret."""
    return URLSafeTimedSerializer(get_session_secret())


def create_session_value(user_id: str) -> str:
    """Return a timestamped signed cookie value for the specified account."""
    return _serializer().dumps(user_id)


def get_current_user(request: Request, db: Session) -> Optional[User]:
    """Resolve the request cookie to a user, returning None if invalid or absent."""
    value = request.cookies.get(SESSION_COOKIE)
    if not value:
        return None
    try:
        user_id = _serializer().loads(
            value,
            max_age=SESSION_MAX_AGE,
        )
    except (BadSignature, SignatureExpired):
        return None
    return db.scalar(select(User).where(User.id == user_id))
