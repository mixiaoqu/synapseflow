"""merge document category migration head with latest indexing head

Revision ID: f2b3c4d5e6f7
Revises: d0e1f2a3b4c5, f1a2b3c4d5e6
Create Date: 2026-04-06

"""

from typing import Sequence, Union

revision: str = "f2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = ("d0e1f2a3b4c5", "f1a2b3c4d5e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
