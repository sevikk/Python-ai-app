import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.db import database
from app.db.database import Base
from app.main import app
from app.services.passwords import hash_password, verify_password
from app.db.models import Conversation
from app.db.auth_models import User


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        database.engine = self.engine
        database.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        database.engine = None
        database.SessionLocal = None
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_password_hash_round_trip(self) -> None:
        password_hash = hash_password("correct-horse")
        self.assertTrue(verify_password("correct-horse", password_hash))
        self.assertFalse(verify_password("wrong-horse", password_hash))

    def test_register_login_me_and_logout(self) -> None:
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
        self.client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "correct-horse"},
        )
        login = self.client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrong-horse"},
        )

        self.assertEqual(login.status_code, 401)

    def test_login_claims_anonymous_conversations(self) -> None:
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
