# HTTP API

This package contains the FastAPI route hierarchy.

## Files and folders

- `__init__.py` — package marker for the API layer.
- `routes/` — routers for chat, authentication, conversation history, and health.

Route handlers translate HTTP input into validated schema objects, call
application services, and convert results or failures into HTTP responses.
Business logic and persistence operations belong in `app/services/`, not here.
