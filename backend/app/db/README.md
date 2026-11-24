# Persistence

SQLAlchemy models and database lifecycle helpers live in this package.

## Files

- `__init__.py` — package marker for database functionality.
- `auth_models.py` — registered user table and account fields.
- `database.py` — declarative base, optional engine, startup migrations, and
  request-scoped sessions.
- `models.py` — conversation and message tables, relationships, and ordering.

The schema is managed by Alembic in `backend/migrations/`; model definitions
provide ORM mappings and metadata. Application startup enables persistence only
when `DATABASE_URL` is configured and reachable.
