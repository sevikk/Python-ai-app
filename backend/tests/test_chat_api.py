"""API tests for chat, task extraction, SSE, and request throttling."""

import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.api_core.exceptions import InvalidArgument

from app.core.rate_limit import InMemoryRateLimiter
from app.main import app
from app.schemas.chat import ChatMessage
from app.schemas.tasks import ExtractedTask, TaskExtractionResponse
from app.services.chat import stream_reply


def user_message(content: str = "Hello") -> dict[str, str]:
    """Build the standard user-message JSON object used by request tests."""
    return {"role": "user", "content": content}


class ChatApiTests(unittest.TestCase):
    """Exercise HTTP routes with provider calls replaced by local fixtures."""

    def setUp(self) -> None:
        """Install test secret and a fresh chat rate limiter for each test."""
        self.session_secret_patch = patch.dict(
            os.environ,
            {"SESSION_SECRET": "test-session-secret-for-backend-tests"},
        )
        self.session_secret_patch.start()
        self.previous_limiter = app.state.chat_rate_limiter
        app.state.chat_rate_limiter = InMemoryRateLimiter(10, 60)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """Close the client and restore the app's original limiter and secret."""
        self.client.close()
        app.state.chat_rate_limiter = self.previous_limiter
        self.session_secret_patch.stop()

    def test_health_endpoint_returns_ok(self) -> None:
        """Expose a successful process-health response."""
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_chat_requires_api_key(self) -> None:
        """Return a service-unavailable error when Gemini is not configured."""
        with patch("app.api.routes.chat.get_gemini_api_key", return_value=None):
            response = self.client.post(
                "/chat",
                json={"messages": [user_message()]},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("GEMINI_API_KEY", response.json()["detail"])

    def test_task_extraction_returns_validated_structured_output(self) -> None:
        """Serialize validated structured task output in the API response."""
        tasks = TaskExtractionResponse(
            tasks=[
                ExtractedTask(
                    title="Send the project brief",
                    priority="high",
                    due_date="2026-12-01",
                )
            ]
        )
        with (
            patch("app.api.routes.chat.get_gemini_api_key", return_value="test-key"),
            patch("app.api.routes.chat.extract_tasks", return_value=tasks) as extract,
        ):
            response = self.client.post(
                "/tasks/extract",
                json={"text": "Send the project brief by December 1, 2026."},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "tasks": [
                    {
                        "title": "Send the project brief",
                        "priority": "high",
                        "due_date": "2026-12-01",
                    }
                ]
            },
        )
        extract.assert_called_once()

    def test_task_extraction_rejects_empty_or_oversized_input(self) -> None:
        """Reject blank and over-limit task text before calling the model."""
        with patch("app.api.routes.chat.extract_tasks") as extract:
            empty_response = self.client.post(
                "/tasks/extract",
                json={"text": " "},
            )
            oversized_response = self.client.post(
                "/tasks/extract",
                json={"text": "x" * 4001},
            )

        self.assertEqual(empty_response.status_code, 422)
        self.assertEqual(oversized_response.status_code, 422)
        extract.assert_not_called()

    def test_task_extraction_reports_model_failures_without_details(self) -> None:
        """Log provider parsing failures but return a sanitized error message."""
        with (
            patch("app.api.routes.chat.get_gemini_api_key", return_value="test-key"),
            patch(
                "app.api.routes.chat.extract_tasks",
                side_effect=ValueError("invalid model output"),
            ),
            self.assertLogs("app.api.routes.chat", level="ERROR"),
        ):
            response = self.client.post(
                "/tasks/extract",
                json={"text": "Finish the report"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn("Tasks could not be extracted", response.json()["detail"])
        self.assertNotIn("invalid model output", response.text)

    def test_chat_returns_generated_reply(self) -> None:
        """Return the generated model text from the synchronous chat route."""
        with (
            patch("app.api.routes.chat.get_gemini_api_key", return_value="test-key"),
            patch(
                "app.api.routes.chat.generate_reply",
                return_value="Hello back",
            ) as generate_reply,
        ):
            response = self.client.post(
                "/chat",
                json={"messages": [user_message()]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"reply": "Hello back"})
        generate_reply.assert_called_once()

    def test_chat_hides_unexpected_provider_errors(self) -> None:
        """Hide unexpected provider exception details from API clients."""
        with (
            patch("app.api.routes.chat.get_gemini_api_key", return_value="test-key"),
            patch(
                "app.api.routes.chat.generate_reply",
                side_effect=RuntimeError("private provider detail"),
            ),
            self.assertLogs("app.api.routes.chat", level="ERROR"),
        ):
            response = self.client.post(
                "/chat",
                json={"messages": [user_message()]},
            )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private provider detail", response.text)

    def test_chat_reports_provider_errors_without_exposing_details(self) -> None:
        """Map known provider errors to a sanitized gateway response."""
        with (
            patch("app.api.routes.chat.get_gemini_api_key", return_value="test-key"),
            patch(
                "app.api.routes.chat.generate_reply",
                side_effect=InvalidArgument("private provider detail"),
            ),
            self.assertLogs("app.api.routes.chat", level="ERROR"),
        ):
            response = self.client.post(
                "/chat",
                json={"messages": [user_message()]},
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn("Gemini API request failed", response.json()["detail"])
        self.assertNotIn("private provider detail", response.text)

    def test_stream_returns_tokens_and_done_event(self) -> None:
        """Emit model chunks and the terminal completion SSE event."""
        requests: list[dict[str, object]] = []

        async def fake_stream_reply(**kwargs: object):
            """Record the provider request and yield a deterministic reply."""
            requests.append(kwargs)
            yield "Hello"
            yield " back"

        with (
            patch("app.api.routes.chat.get_gemini_api_key", return_value="test-key"),
            patch("app.api.routes.chat.stream_reply", fake_stream_reply),
        ):
            response = self.client.post(
                "/chat/stream",
                json={"messages": [user_message()]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('"token": "Hello"', response.text)
        self.assertIn('"token": " back"', response.text)
        self.assertIn('"done": true', response.text)
        self.assertEqual(requests[0]["api_key"], "test-key")

    def test_stream_reports_provider_failure_as_sse_error(self) -> None:
        """Convert streaming failures to sanitized SSE error events."""
        class FailingAsyncIterator:
            """Async iterator fixture that fails as soon as it is consumed."""

            def __aiter__(self) -> "FailingAsyncIterator":
                """Return this object as its own asynchronous iterator."""
                return self

            async def __anext__(self) -> str:
                """Raise the simulated provider failure."""
                raise RuntimeError("private provider detail")

        def failing_stream(**kwargs: object) -> FailingAsyncIterator:
            """Return the failing iterator without using provider arguments."""
            del kwargs
            return FailingAsyncIterator()

        with (
            patch("app.api.routes.chat.get_gemini_api_key", return_value="test-key"),
            patch("app.api.routes.chat.stream_reply", failing_stream),
            self.assertLogs("app.api.routes.chat", level="ERROR"),
        ):
            response = self.client.post(
                "/chat/stream",
                json={"messages": [user_message()]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("response stream failed", response.text)
        self.assertNotIn("private provider detail", response.text)

    def test_stream_closes_provider_iterator_when_consumer_stops(self) -> None:
        """Close the underlying provider stream when the client cancels early."""
        closed = False

        async def chunks():
            """Yield two chunks and record when stream cleanup runs."""
            nonlocal closed
            try:
                yield SimpleNamespace(content="partial")
                yield SimpleNamespace(content="unconsumed")
            finally:
                closed = True

        class FakeModel:
            """Expose a controlled async stream for the service test."""

            def astream(self, _messages: object):
                """Return the fixture chunk stream for any prompt."""
                return chunks()

        async def stop_after_first_chunk() -> None:
            """Consume one response chunk and explicitly cancel the wrapper."""
            with patch(
                "app.services.chat._create_model",
                return_value=FakeModel(),
            ):
                stream = stream_reply(
                    [ChatMessage(role="user", content="Hello")],
                    api_key="test-key",
                    model_name="test-model",
                )
                self.assertEqual(await stream.__anext__(), "partial")
                await stream.aclose()

        asyncio.run(stop_after_first_chunk())
        self.assertTrue(closed)

    def test_request_validation_rejects_too_many_messages(self) -> None:
        """Reject chat context lists exceeding the API limit."""
        response = self.client.post(
            "/chat",
            json={"messages": [user_message() for _ in range(21)]},
        )

        self.assertEqual(response.status_code, 422)

    def test_request_validation_rejects_oversized_message(self) -> None:
        """Reject messages exceeding the configured content length."""
        response = self.client.post(
            "/chat/stream",
            json={"messages": [user_message("x" * 4001)]},
        )

        self.assertEqual(response.status_code, 422)

    def test_rate_limit_is_shared_by_chat_endpoints(self) -> None:
        """Share one rate-limit budget between synchronous and SSE endpoints."""
        app.state.chat_rate_limiter = InMemoryRateLimiter(1, 60)
        with (
            patch("app.api.routes.chat.get_gemini_api_key", return_value="test-key"),
            patch("app.api.routes.chat.generate_reply", return_value="Hello"),
        ):
            first_response = self.client.post(
                "/chat",
                json={"messages": [user_message()]},
            )
            limited_response = self.client.post(
                "/chat/stream",
                json={"messages": [user_message()]},
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(limited_response.status_code, 429)
        self.assertGreaterEqual(
            int(limited_response.headers["Retry-After"]),
            1,
        )

    def test_rate_limit_expires_after_its_window(self) -> None:
        """Allow another request once the rolling time window has elapsed."""
        with patch(
            "app.core.rate_limit.time.monotonic",
            side_effect=[0, 0, 5, 61],
        ):
            limiter = InMemoryRateLimiter(1, 60)
            self.assertIsNone(limiter.check("client"))
            self.assertEqual(limiter.check("client"), 55)
            self.assertIsNone(limiter.check("client"))


if __name__ == "__main__":
    unittest.main()
