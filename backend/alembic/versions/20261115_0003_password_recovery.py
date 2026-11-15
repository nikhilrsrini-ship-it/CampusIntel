"""Add single-use password recovery tokens and per-user auth token version."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261115_0003"
down_revision: Union[str, None] = "20261113_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_token_version", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("users", "auth_token_version", server_default=None)
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_user_created", "password_reset_tokens", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_user_created", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "auth_token_version")
