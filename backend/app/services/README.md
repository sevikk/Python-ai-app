# Application services

Reusable operations used by API handlers are implemented here.

## Files

- `__init__.py` — package marker for service modules.
- `auth.py` — signed session-cookie creation and current-user lookup.
- `chat.py` — LangChain/Gemini calls, message conversion, streaming, and
  structured task extraction.
- `conversations.py` — ownership-aware persistence, history retrieval, message
  replacement, anonymous-chat claiming, and cleanup.
- `passwords.py` — salted PBKDF2 password hashing and verification.

Services keep provider and persistence details out of route handlers. They
raise errors to callers; HTTP status mapping and client-safe response messages
are handled by the API layer.
