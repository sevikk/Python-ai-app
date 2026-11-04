import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.api_core.exceptions import InvalidArgument

from app.core.rate_limit import InMemoryRateLimiter
from app.main import app


def user_message(content: str = "Hello") -> dict[str, str]:
    return {"role": "user", "content": content}


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_limiter = app.state.chat_rate_limiter
        app.state.chat_rate_limiter = InMemoryRateLimiter(10, 60)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.state.chat_rate_limiter = self.previous_limiter

    def test_health_endpoint_returns_ok(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_chat_requires_api_key(self) -> None:
        with patch("app.api.routes.chat.get_gemini_api_key", return_value=None):
            response = self.client.post(
                "/chat",
                json={"messages": [user_message()]},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("GEMINI_API_KEY", response.json()["detail"])

    def test_chat_returns_generated_reply(self) -> None:
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
        requests: list[dict[str, object]] = []

        async def fake_stream_reply(**kwargs: object):
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
        self.assertIn('"done":true', response.text)
        self.assertEqual(requests[0]["api_key"], "test-key")

    def test_stream_reports_provider_failure_as_sse_error(self) -> None:
        class FailingAsyncIterator:
            def __aiter__(self) -> "FailingAsyncIterator":
                return self

            async def __anext__(self) -> str:
                raise RuntimeError("private provider detail")

        def failing_stream(**kwargs: object) -> FailingAsyncIterator:
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

    def test_request_validation_rejects_too_many_messages(self) -> None:
        response = self.client.post(
            "/chat",
            json={"messages": [user_message() for _ in range(21)]},
        )

        self.assertEqual(response.status_code, 422)

    def test_request_validation_rejects_oversized_message(self) -> None:
        response = self.client.post(
            "/chat/stream",
            json={"messages": [user_message("x" * 4001)]},
        )

        self.assertEqual(response.status_code, 422)

    def test_rate_limit_is_shared_by_chat_endpoints(self) -> None:
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
