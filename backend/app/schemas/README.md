# API schemas

Pydantic models define validation and serialization for backend API data.

## Files

- `__init__.py` — package marker for schema modules.
- `auth.py` — authentication credentials and public user response.
- `chat.py` — chat messages, chat requests, and non-streaming response.
- `conversations.py` — saved conversation and message response shapes.
- `tasks.py` — task-extraction input, task fields, and structured result.

These models are the boundary between untrusted HTTP/model data and the
application. Field descriptions document the meaning of individual API fields;
validators enforce constraints that cannot be represented by basic types.
