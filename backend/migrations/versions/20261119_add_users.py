"""Add registered users and optional conversation ownership.

Revision ID: 20261119_add_users
Revises: 20261119_initial
"""

from alembic import op
import sqlalchemy as sa

# Alembic identifiers describe this migration and its parent in the revision graph.
revision = "20261119_add_users"
down_revision = "20261119_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user accounts and add an optional owner foreign key to chats."""
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.add_column(
        "conversations",
        sa.Column("owner_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_conversations_owner_id",
        "conversations",
        ["owner_id"],
    )
    op.create_foreign_key(
        "fk_conversations_owner_id_users",
        "conversations",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove ownership and account structures in dependency-safe order."""
    op.drop_constraint(
        "fk_conversations_owner_id_users",
        "conversations",
        type_="foreignkey",
    )
    op.drop_index("ix_conversations_owner_id", table_name="conversations")
    op.drop_column("conversations", "owner_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
