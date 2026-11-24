"""SQLAlchemy model for registered account records."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    """An account used to authenticate and own saved conversations."""

    __tablename__ = "users"

    # Stable account identifier referenced by owned conversations.
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID identifying this account.",
    )
    # Unique normalized email used as the login name.
    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
        comment="Unique normalized email address for account sign-in.",
    )
    # One-way password verifier; raw passwords are never stored.
    password_hash: Mapped[str] = mapped_column(
        String(255),
        comment="Salted PBKDF2 hash used to verify account passwords.",
    )
    # Creation timestamp used for account record auditing.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Time when the account was created.",
    )
