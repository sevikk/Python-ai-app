# Database migrations

Alembic controls database schema changes independently from application
startup and ORM model loading.

## Files and folders

- `env.py` — loads ORM metadata and configures online or offline migration runs.
- `script.py.mako` — template for newly generated Alembic revision files.
- `versions/` — ordered, reversible schema revisions.

Application startup applies pending revisions when PostgreSQL is configured.
Changes to ORM models that affect the database should be represented by a new
revision in `versions/`, rather than by editing an already applied migration.
