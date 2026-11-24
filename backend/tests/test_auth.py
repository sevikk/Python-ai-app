"""Integration tests for account authentication and session configuration."""

import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.core.rate_limit import InMemoryRateLimiter
from app.db import database
from app.db.database import Base
from app.main import app
from app.services.passwords import hash_password, verify_password
from app.db.models import Conversation
from app.db.auth_models import User
from app.core.config import get_session_secret


class AuthTests(unittest.TestCase):
    """Exercise auth routes against an isolated in-memory SQLite database."""

    def setUp(self) -> None:
        """Install test secrets, isolated limiters, and a temporary database."""
        # Temporary signing secret lets route tests exercise session cookies.
        self.session_secret_patch = patch.dict(
            os.environ,
            {"SESSION_SECRET": "test-session-secret-for-backend-tests"},
        )
        self.session_secret_patch.start()
        # Preserve and restore process-wide limits after each test.
        self.previous_auth_ip_limiter = app.state.auth_ip_rate_limiter
        self.previous_auth_pair_limiter = app.state.auth_pair_rate_limiter
        app.state.auth_ip_rate_limiter = InMemoryRateLimiter(30, 900)
        app.state.auth_pair_rate_limiter = InMemoryRateLimiter(5, 900)
        # SQLite engine and session factory isolate persistence from PostgreSQL.
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        database.engine = self.engine
        # Handlers use this factory to open sessions during HTTP requests.
        database.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        # TestClient drives the FastAPI routes synchronously.
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """Restore shared application state and dispose the test database."""
        self.client.close()
        app.state.auth_ip_rate_limiter = self.previous_auth_ip_limiter
        app.state.auth_pair_rate_limiter = self.previous_auth_pair_limiter
        database.engine = None
        database.SessionLocal = None
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self.session_secret_patch.stop()

    def test_session_secret_must_be_present_and_long_enough(self) -> None:
        """Require a nonempty signing key of at least 32 characters."""
        for secret in ("", "too-short"):
            with self.subTest(secret=secret), patch.dict(
                os.environ,
                {"SESSION_SECRET": secret},
            ), self.assertRaisesRegex(ValueError, "at least 32 characters"):
                get_session_secret()

        with patch.dict(
            os.environ,
            {"SESSION_SECRET": "0123456789abcdef0123456789abcdef"},
        ):
            self.assertEqual(
                get_session_secret(),
                "0123456789abcdef0123456789abcdef",
            )

    def test_application_startup_rejects_missing_session_secret(self) -> None:
        """Fail the FastAPI lifespan before startup when the key is missing."""
        async def start_application() -> None:
            """Run the app lifespan to exercise its startup validation."""
            async with app.router.lifespan_context(app):
                pass

        with (
            patch.dict(os.environ, {"SESSION_SECRET": ""}),
            self.assertRaisesRegex(ValueError, "at least 32 characters"),
        ):
            asyncio.run(start_application())

    def test_password_hash_round_trip(self) -> None:
        """Accept the original password and reject a different password."""
        password_hash = hash_password("correct-horse")
        self.assertTrue(verify_password("correct-horse", password_hash))
        self.assertFalse(verify_password("wrong-horse", password_hash))

    def test_register_login_me_and_logout(self) -> None:
        """Cover account creation, cookie authentication, and logout."""
        register = self.client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "correct-horse"},
        )
        self.assertEqual(register.status_code, 201)
        self.assertIn("ai_chat_session", register.cookies)

        me = self.client.get("/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "test@example.com")

        logout = self.client.post("/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.json(), {"logged_out": True})

        me_after_logout = self.client.get("/auth/me")
        self.assertEqual(me_after_logout.status_code, 401)

    def test_duplicate_registration_is_rejected(self) -> None:
        """Return a conflict when an email address is already registered."""
        first = self.client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "correct-horse"},
        )
        second = self.client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "another-pass"},
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

    def test_login_rejects_wrong_password(self) -> None:
        """Reject invalid credentials without issuing an auth session."""
        self.client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "correct-horse"},
        )
        login = self.client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrong-horse"},
        )

        self.assertEqual(login.status_code, 401)

    def test_authentication_is_limited_by_normalized_email_and_ip(self) -> None:
        """Share the pair limit across endpoints and normalize email casing."""
        app.state.auth_pair_rate_limiter = InMemoryRateLimiter(1, 900)
        first = self.client.post(
            "/auth/login",
            json={"email": "User@example.com", "password": "wrong-pass"},
        )
        limited = self.client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "correct-horse"},
        )
        different_email = self.client.post(
            "/auth/login",
            json={"email": "other@example.com", "password": "wrong-pass"},
        )

        self.assertEqual(first.status_code, 401)
        self.assertEqual(limited.status_code, 429)
        self.assertIn("Retry-After", limited.headers)
        self.assertEqual(different_email.status_code, 401)

    def test_authentication_has_a_separate_per_ip_limit(self) -> None:
        """Limit attempts from one client even when email addresses differ."""
        app.state.auth_ip_rate_limiter = InMemoryRateLimiter(1, 900)
        first = self.client.post(
            "/auth/login",
            json={"email": "first@example.com", "password": "wrong-pass"},
        )
        limited = self.client.post(
            "/auth/login",
            json={"email": "second@example.com", "password": "wrong-pass"},
        )

        self.assertEqual(first.status_code, 401)
        self.assertEqual(limited.status_code, 429)

    def test_login_claims_anonymous_conversations(self) -> None:
        """Transfer chats for the browser session to the new account owner."""
        with database.SessionLocal() as db:
            db.add(
                Conversation(
                    session_id="browser-session",
                    title="Anonymous chat",
                )
            )
            db.commit()

        self.client.post(
            "/auth/register",
            headers={"X-Session-ID": "browser-session"},
            json={"email": "owner@example.com", "password": "correct-horse"},
        )

        with database.SessionLocal() as db:
            conversation = db.query(Conversation).filter(
                Conversation.session_id == "browser-session"
            ).one()
            user = db.scalar(
                select(User).where(User.email == "owner@example.com")
            )
            self.assertIsNotNone(user)
            self.assertEqual(conversation.owner_id, user.id)


if __name__ == "__main__":
    unittest.main()
