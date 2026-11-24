# Backend tests

The test suite verifies HTTP behavior, validation, authentication, throttling,
and database service operations without requiring live model-provider calls.

## Files

- `__init__.py` — marks the test directory as a Python package.
- `test_auth.py` — account lifecycle, password checks, signing-secret validation,
  and authentication limits.
- `test_chat_api.py` — chat and task endpoints, SSE behavior, request validation,
  and chat rate limits.
- `test_conversations.py` — conversation ownership and persistence operations
  against SQLite.
- `test_task_extraction.py` — structured model output conversion and schema
  validation using local fakes.

Run all tests from `backend/` with
`./.venv/bin/python -m unittest discover -s tests` (or use the active virtual
environment's Python executable).
