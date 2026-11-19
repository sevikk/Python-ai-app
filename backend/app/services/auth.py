from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_session_secret
from app.db.auth_models import User

SESSION_COOKIE = "ai_chat_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_session_secret())


def create_session_value(user_id: str) -> str:
    return _serializer().dumps(user_id)


def get_current_user(request: Request, db: Session) -> Optional[User]:
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
