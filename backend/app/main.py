from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, chat, conversations, health
from app.core.config import (
    get_auth_ip_rate_limit,
    get_auth_rate_limit,
    get_auth_rate_window_seconds,
    get_chat_rate_limit,
    get_chat_rate_window_seconds,
    get_cors_origins,
    get_session_secret,
)
from app.core.rate_limit import InMemoryRateLimiter
from app.db.database import init_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_session_secret()
    init_database()
    yield


app = FastAPI(title="AI Chat API", lifespan=lifespan)
app.state.chat_rate_limiter = InMemoryRateLimiter(
    limit=get_chat_rate_limit(),
    window_seconds=get_chat_rate_window_seconds(),
)
app.state.auth_ip_rate_limiter = InMemoryRateLimiter(
    limit=get_auth_ip_rate_limit(),
    window_seconds=get_auth_rate_window_seconds(),
)
app.state.auth_pair_rate_limiter = InMemoryRateLimiter(
    limit=get_auth_rate_limit(),
    window_seconds=get_auth_rate_window_seconds(),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(auth.router)
