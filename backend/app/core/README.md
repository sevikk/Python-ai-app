# Core infrastructure

Shared configuration and cross-cutting request controls live here.

## Files

- `__init__.py` — package marker for core backend utilities.
- `config.py` — reads environment settings, applies defaults, and validates
  numeric limits and the session signing secret.
- `rate_limit.py` — thread-safe in-memory sliding-window limiters and FastAPI
  enforcement helpers for chat and authentication.

Rate-limit state is process-local; deployments with multiple workers or
instances need a shared storage backend to coordinate limits.
