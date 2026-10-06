"""add_repository_health_and_status_fields

Revision ID: 05796d69f050
Revises: 4abdfcb7d7a9
Create Date: 2026-09-30 12:16:54.688297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05796d69f050'
down_revision: Union[str, Sequence[str], None] = '4abdfcb7d7a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
