# Backend

FastAPI backend for the AI chat application. It exposes chat and account APIs,
calls Gemini through LangChain, and optionally persists conversation history in
PostgreSQL using SQLAlchemy and Alembic.

## Files and folders

- `.env.example` — names and development defaults for supported environment
  settings. Copy it to a local `.env`; keep secrets out of version control.
- `.env` — local-only environment values and secrets; ignored by Git and never
  documented or committed with their contents.
- `Dockerfile` — builds the Python API container and starts its ASGI app.
- `alembic.ini` — Alembic migration runner configuration; the database URL is
  supplied from the environment.
- `requirements.txt` — Python runtime dependencies.
- `app/` — application code, organized by API, configuration, schemas,
  persistence, and services.
- `migrations/` — versioned database schema changes and Alembic environment.
- `tests/` — automated API and persistence tests.

## Architecture

`app/main.py` validates critical configuration, initializes persistence, and
registers routers. Routes validate HTTP requests and coordinate services.
Services contain model, authentication, and conversation operations; Pydantic
schemas define the API contract; SQLAlchemy models define persisted data.

Database migrations run during application startup when `DATABASE_URL` is
configured. Without it, chat generation can run without persistent history;
database-dependent account and history operations are unavailable.
