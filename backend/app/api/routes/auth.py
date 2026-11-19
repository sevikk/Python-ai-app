from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_auth_cookie_secure
from app.db.auth_models import User
from app.db.database import get_db
from app.schemas.auth import AuthRequest, UserResponse
from app.services.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_value,
    get_current_user,
)
from app.services.passwords import hash_password, verify_password
from app.services.conversations import claim_anonymous_conversations

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    auth_request: AuthRequest,
    response: Response,
    x_session_id: str = Header("anonymous", alias="X-Session-ID"),
    db: Session = Depends(get_db),
) -> UserResponse:
    email = str(auth_request.email).strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(
        email=email,
        password_hash=hash_password(auth_request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if x_session_id != "anonymous":
        claim_anonymous_conversations(db, x_session_id, user.id)
    _set_auth_cookie(response, user.id)
    return UserResponse(id=user.id, email=user.email)


@router.post("/login", response_model=UserResponse)
def login(
    auth_request: AuthRequest,
    response: Response,
    x_session_id: str = Header("anonymous", alias="X-Session-ID"),
    db: Session = Depends(get_db),
) -> UserResponse:
    email = str(auth_request.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(
        auth_request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if x_session_id != "anonymous":
        claim_anonymous_conversations(db, x_session_id, user.id)
    _set_auth_cookie(response, user.id)
    return UserResponse(id=user.id, email=user.email)


@router.get("/me", response_model=UserResponse)
def me(
    request: Request,
    db: Session = Depends(get_db),
) -> UserResponse:
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    return UserResponse(id=user.id, email=user.email)


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        samesite="none" if get_auth_cookie_secure() else "lax",
        secure=get_auth_cookie_secure(),
    )
    return {"logged_out": True}


def _set_auth_cookie(response: Response, user_id: str) -> None:
    secure = get_auth_cookie_secure()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_value(user_id),
        httponly=True,
        samesite="none" if secure else "lax",
        secure=secure,
        max_age=SESSION_MAX_AGE,
        path="/",
    )
