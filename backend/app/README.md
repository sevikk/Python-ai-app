# Application package

The `app` package is the FastAPI application layer.

## Files and folders

- `__init__.py` — marks this directory as the backend Python package.
- `main.py` — composes the FastAPI app, lifecycle, middleware, and routers.
- `api/` — HTTP route modules.
- `core/` — environment configuration and shared rate-limiting infrastructure.
- `db/` — SQLAlchemy models, engine lifecycle, and request sessions.
- `schemas/` — validated request and response data models.
- `services/` — application operations used by routes.

## Request flow

Requests enter through routers in `api/routes/`; those routes use `schemas/`
for validation and call `services/`. Services use `db/` for persistence and
`core/` for configuration or shared controls. `main.py` assembles these
components into the ASGI application.
