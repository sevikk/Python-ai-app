import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.schemas.tasks import TaskExtractionResponse
from app.services.chat import extract_tasks


class StructuredTaskRunnable:
    def __init__(self, result: object = None) -> None:
        self.result = result
        self.messages: object = None

    def invoke(self, messages: object) -> object:
        self.messages = messages
        return self.result


class TaskExtractionTests(unittest.TestCase):
    def test_extract_tasks_uses_pydantic_structured_output(self) -> None:
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
            def with_structured_output(
                self,
                schema: type[TaskExtractionResponse],
                method: str,
            ) -> StructuredTaskRunnable:
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
        runnable = StructuredTaskRunnable(
            {"tasks": [{"title": "", "priority": "urgent", "due_date": "soon"}]}
        )

        class FakeModel:
            def with_structured_output(
                self,
                schema: type[TaskExtractionResponse],
                method: str,
            ) -> StructuredTaskRunnable:
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
