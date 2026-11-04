import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def get_cors_origins() -> list[str]:
    origins = os.getenv("CORS_ORIGINS", "http://localhost:4200")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def get_gemini_api_key() -> Optional[str]:
    return os.getenv("GEMINI_API_KEY")


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def _get_positive_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer.") from error
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed


def get_chat_rate_limit() -> int:
    return _get_positive_int("CHAT_RATE_LIMIT", 10)


def get_chat_rate_window_seconds() -> int:
    return _get_positive_int("CHAT_RATE_WINDOW_SECONDS", 60)
