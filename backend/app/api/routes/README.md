# API routes

Each module owns a set of related HTTP endpoints.

## Files

- `__init__.py` — package marker for route modules.
- `auth.py` — registration, login, current-user lookup, logout, and cookie issue.
- `chat.py` — synchronous chat, server-sent event streaming, and task extraction.
- `conversations.py` — list, read, and delete conversations with ownership checks.
- `health.py` — process and database health probes.

The chat router applies its shared rate limit to chat and extraction endpoints.
Authentication routes enforce their own IP and IP/email limits. Conversation
routes authorize every read or deletion through the current account or browser
session identity.
