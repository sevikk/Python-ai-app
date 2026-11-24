"""Persistence tests for chat ownership and ordered conversation history."""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.auth_models import User
from app.schemas.chat import ChatMessage
from app.services.conversations import (
    claim_anonymous_conversations,
    delete_conversation,
    delete_empty_conversations,
    get_conversation,
    get_or_create_conversation,
    list_conversations,
    replace_conversation_messages,
)


class ConversationPersistenceTests(unittest.TestCase):
    """Verify conversation service operations against isolated SQLite tables."""

    def setUp(self) -> None:
        """Create a fresh in-memory database for each persistence test."""
        # Engine owns the isolated SQLite schema for this test instance.
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        # Session factory and active session are the service test's DB handles.
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self) -> None:
        """Close the session and remove the temporary database schema."""
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_creates_lists_loads_and_deletes_conversation(self) -> None:
        """Persist messages, list and retrieve their thread, then delete it."""
        conversation = get_or_create_conversation(
            self.db,
            "session-a",
            None,
        )
        replace_conversation_messages(
            self.db,
            conversation,
            [
                ChatMessage(role="user", content="Hello"),
                ChatMessage(role="assistant", content="Hi"),
            ],
        )

        conversations = list_conversations(self.db, "session-a")
        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0].title, "Hello")

        loaded = get_conversation(
            self.db,
            "session-a",
            conversation.id,
        )
        self.assertIsNotNone(loaded)
        self.assertEqual(
            [message.content for message in loaded.messages],
            ["Hello", "Hi"],
        )

        self.assertTrue(
            delete_conversation(self.db, "session-a", conversation.id),
        )
        self.assertIsNone(
            get_conversation(self.db, "session-a", conversation.id),
        )

    def test_conversation_is_private_to_session(self) -> None:
        """Prevent another anonymous browser session from reading or deleting."""
        conversation = get_or_create_conversation(
            self.db,
            "session-a",
            None,
        )
        replace_conversation_messages(
            self.db,
            conversation,
            [ChatMessage(role="user", content="Private")],
        )

        self.assertIsNone(
            get_conversation(self.db, "session-b", conversation.id),
        )
        self.assertFalse(
            delete_conversation(self.db, "session-b", conversation.id),
        )

    def test_empty_conversations_are_cleaned_up(self) -> None:
        """Delete empty placeholders while retaining conversations with messages."""
        get_or_create_conversation(self.db, "session-a", None)
        conversation = get_or_create_conversation(
            self.db,
            "session-a",
            None,
        )
        replace_conversation_messages(
            self.db,
            conversation,
            [ChatMessage(role="user", content="Complete")],
        )

        deleted = delete_empty_conversations(self.db)

        self.assertEqual(deleted, 1)
        conversations = list_conversations(self.db, "session-a")
        self.assertEqual(len(conversations), 1)

    def test_anonymous_conversations_can_be_claimed_by_owner(self) -> None:
        """Move anonymous chats to an account and hide them from the old session."""
        conversation = get_or_create_conversation(
            self.db,
            "session-a",
            None,
        )
        replace_conversation_messages(
            self.db,
            conversation,
            [ChatMessage(role="user", content="Claim me")],
        )
        user = User(
            email="owner@example.com",
            password_hash="test-hash",
        )
        self.db.add(user)
        self.db.commit()

        claimed = claim_anonymous_conversations(
            self.db,
            "session-a",
            user.id,
        )

        self.assertEqual(claimed, 1)
        owned = list_conversations(self.db, "session-b", user.id)
        self.assertEqual(len(owned), 1)
        self.assertIsNotNone(
            get_conversation(
                self.db,
                "session-b",
                conversation.id,
                user.id,
            ),
        )
        self.assertIsNone(
            get_conversation(
                self.db,
                "session-a",
                conversation.id,
                None,
            ),
        )


if __name__ == "__main__":
    unittest.main()
