"""Initial schema migration marker for the foundation milestone.

Revision ID: 20261113_0001
Revises:
Create Date: 2026-11-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261113_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Application tables are introduced with the database-model milestone.
    pass


def downgrade() -> None:
    pass
