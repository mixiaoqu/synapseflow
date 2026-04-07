"""merge chat memory and pg_trgm migration heads

Revision ID: f4d5e6f7a8b9
Revises: a9b8c7d6e5f4, f3c4d5e6f7a8
Create Date: 2026-04-07

"""

from typing import Sequence, Union

revision: str = "f4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = ("a9b8c7d6e5f4", "f3c4d5e6f7a8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
