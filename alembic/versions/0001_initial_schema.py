"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-03-17

Baseline migration — no tables yet. Business tables are added in Phase 1
(Shopify integration) and Phase 2 (reconciliation engine).

The alembic_version table itself is created by Alembic automatically when
`alembic upgrade head` is run for the first time.
"""

from typing import Sequence, Union

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # No tables in baseline — added per phase


def downgrade() -> None:
    pass
