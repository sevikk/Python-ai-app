"""Unit tests for structured task extraction and response validation."""

import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.schemas.tasks import TaskExtractionResponse
from app.services.chat import extract_tasks


class StructuredTaskRunnable:
    """Minimal stand-in that captures model input and returns configured output."""

    def __init__(self, result: object = None) -> None:
        """Store the fake result and initialize captured-message state."""
        # Configured model response returned by invoke().
        self.result = result
        # Prompt captured from the extraction service for assertion.
        self.messages: object = None

    def invoke(self, messages: object) -> object:
        """Capture the model prompt and return the configured fixture."""
        self.messages = messages
        return self.result


class TaskExtractionTests(unittest.TestCase):
    """Test the extraction service without making external model requests."""

    def test_extract_tasks_uses_pydantic_structured_output(self) -> None:
        """Use Gemini's structured-output interface and return validated tasks."""
        runnable = StructuredTaskRunnable(
            {
                "tasks": [
                    {
                        "title": "Send the project brief",
                        "priority": "high",
                        "due_date": "2026-12-01",
                    }
                ]
            }
        )
        structured_output_calls: list[tuple[type[TaskExtractionResponse], str]] = []

        class FakeModel:
            """Expose only the structured-output operation used by the service."""

            def with_structured_output(
                self,
                schema: type[TaskExtractionResponse],
                method: str,
            ) -> StructuredTaskRunnable:
                """Record the selected schema and return the test runnable."""
                structured_output_calls.append((schema, method))
                return runnable

        with patch("app.services.chat._create_model", return_value=FakeModel()):
            result = extract_tasks(
                text="Send the project brief by December 1, 2026.",
                api_key="test-key",
                model_name="test-model",
            )

        self.assertIsInstance(result, TaskExtractionResponse)
        self.assertEqual(result.tasks[0].title, "Send the project brief")
        self.assertEqual(str(result.tasks[0].due_date), "2026-12-01")
        self.assertEqual(
            structured_output_calls,
            [(TaskExtractionResponse, "function_calling")],
        )
        self.assertIn(
            ("human", "Send the project brief by December 1, 2026."),
            runnable.messages,
        )

    def test_extract_tasks_rejects_invalid_structured_data(self) -> None:
        """Propagate schema validation errors for malformed model output."""
        runnable = StructuredTaskRunnable(
            {"tasks": [{"title": "", "priority": "urgent", "due_date": "soon"}]}
        )

        class FakeModel:
            """Return invalid fixture data through the structured-output API."""

            def with_structured_output(
                self,
                schema: type[TaskExtractionResponse],
                method: str,
            ) -> StructuredTaskRunnable:
                """Ignore schema parameters and return the invalid fixture."""
                del schema, method
                return runnable

        with (
            patch("app.services.chat._create_model", return_value=FakeModel()),
            self.assertRaises(ValidationError),
        ):
            extract_tasks(
                text="Do the thing urgently.",
                api_key="test-key",
                model_name="test-model",
            )


if __name__ == "__main__":
    unittest.main()
