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
