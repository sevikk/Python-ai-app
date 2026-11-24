"""SQLAlchemy base, engine lifecycle, migrations, and request DB sessions."""

import logging
from collections.abc import Generator
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_database_url

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models and Alembic metadata."""

    pass


# Engine and session factory are initialized only when DATABASE_URL is configured.
engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker[Session]] = None


# Import models so Base.metadata knows every table before create_all().
from app.db import models as _models  # noqa: E402,F401
from app.db import auth_models as _auth_models  # noqa: E402,F401


def init_database() -> None:
    """Connect to PostgreSQL, apply migrations, and prepare local sessions."""
    global engine, SessionLocal
    database_url = get_database_url()
    if not database_url:
        return

    try:
        candidate_engine = create_engine(database_url, pool_pre_ping=True)
        with candidate_engine.connect():
            pass
    except Exception:
        logger.exception(
            "PostgreSQL is unavailable; chat will continue without history persistence."
        )
        engine = None
        SessionLocal = None
        return

    try:
        from alembic import command
        from alembic.config import Config

        backend_dir = Path(__file__).resolve().parents[2]
        alembic_config = Config(str(backend_dir / "alembic.ini"))
        alembic_config.set_main_option(
            "sqlalchemy.url",
            database_url,
        )
        inspector = inspect(candidate_engine)
        existing_tables = set(inspector.get_table_names())
        has_history_tables = bool(
            {"conversations", "messages"} & existing_tables
        )
        has_alembic_table = "alembic_version" in existing_tables
        if has_history_tables and not has_alembic_table:
            command.stamp(alembic_config, "20261119_initial")
            command.upgrade(alembic_config, "head")
        else:
            command.upgrade(alembic_config, "head")

    except Exception:
        candidate_engine.dispose()
        logger.exception("Could not migrate the PostgreSQL schema.")
        raise

    try:
        engine = candidate_engine
        SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )
        from app.services.conversations import delete_empty_conversations

        cleanup_session = SessionLocal()
        try:
            delete_empty_conversations(cleanup_session)
        except Exception:
            logger.exception("Could not clean empty chat conversations.")
        finally:
            cleanup_session.close()
    except Exception:
        candidate_engine.dispose()
        logger.exception(
            "Could not initialize PostgreSQL persistence."
        )
        engine = None
        SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    """Yield one request-scoped database session and always close it."""
    if SessionLocal is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="PostgreSQL is not configured.",
        )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
