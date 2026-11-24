# Migration revisions

Alembic revision scripts define forward and reverse database changes.

## Files

- `20261119_initial_chat_history.py` — creates conversation and message tables,
  indexes, and per-conversation message ordering.
- `20261119_add_users.py` — creates user accounts and adds optional ownership
  of existing conversations.

Each `upgrade()` applies one revision; `downgrade()` reverses it. Revision IDs
and parent IDs form the migration dependency graph. Add new revisions for
future schema changes instead of rewriting revisions already deployed.
