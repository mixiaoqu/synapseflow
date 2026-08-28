"""merge_category_parent_and_graph_heads

Revision ID: 252a9a952580
Revises: 3a4b5c6d7e8f, ff7a8b9c0d1e
Create Date: 2026-05-26 10:10:44.228607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '252a9a952580'
down_revision: Union[str, None] = ('3a4b5c6d7e8f', 'ff7a8b9c0d1e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
