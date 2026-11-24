"""Read and validate backend settings from environment variables and .env."""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def get_cors_origins() -> list[str]:
    """Return configured browser origins as a trimmed list."""
    origins = os.getenv("CORS_ORIGINS", "http://localhost:4200")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def get_gemini_api_key() -> Optional[str]:
    """Return the optional Gemini credential used for model requests."""
    return os.getenv("GEMINI_API_KEY")


def get_gemini_model() -> str:
    """Return the configured Gemini model name or its application default."""
    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def _get_positive_int(name: str, default: int) -> int:
    """Parse a positive integer setting and reject invalid configuration."""
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer.") from error
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed


def get_chat_rate_limit() -> int:
    """Return the maximum chat requests allowed during the chat rate window."""
    return _get_positive_int("CHAT_RATE_LIMIT", 10)


def get_chat_rate_window_seconds() -> int:
    """Return the chat request rate-limit window length in seconds."""
    return _get_positive_int("CHAT_RATE_WINDOW_SECONDS", 60)


def get_auth_rate_limit() -> int:
    """Return the authentication limit for one IP and normalized email pair."""
    return _get_positive_int("AUTH_RATE_LIMIT", 5)


def get_auth_rate_window_seconds() -> int:
    """Return the authentication rate-limit window length in seconds."""
    return _get_positive_int("AUTH_RATE_WINDOW_SECONDS", 900)


def get_auth_ip_rate_limit() -> int:
    """Return the authentication request limit shared by one client IP."""
    return _get_positive_int("AUTH_IP_RATE_LIMIT", 30)


def get_database_url() -> Optional[str]:
    """Return DATABASE_URL in the SQLAlchemy psycopg driver format."""
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_session_secret() -> str:
    """Return the signing secret, rejecting missing or undersized values."""
    secret = os.getenv("SESSION_SECRET", "").strip()
    if len(secret) < 32:
        raise ValueError(
            "SESSION_SECRET must be set to a secret of at least 32 characters."
        )
    return secret


def get_auth_cookie_secure() -> bool:
    """Return whether authentication cookies must use the Secure attribute."""
    return os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
