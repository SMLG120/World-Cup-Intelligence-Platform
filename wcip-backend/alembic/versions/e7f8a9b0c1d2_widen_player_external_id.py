"""widen players.external_id to 255

The squad-ratings import builds ids like
``player-rating:IRN:30/10/2000:<full-name-slug>``; one real 2026 squad name
produces a 90-character id. SQLite ignores VARCHAR lengths, so this only
failed on Postgres, where it aborted ``scripts.bootstrap_data`` (and therefore
the Render start script) with StringDataRightTruncation.

Widening a varchar is a metadata-only change in Postgres (no table rewrite,
no data change), so this is safe on a live database.

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-11-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.alter_column(
            "external_id",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade() -> None:
    # Fails (rather than truncating data) if any stored id is longer than 80
    # characters; shorten or clear those ids first if a downgrade is needed.
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.alter_column(
            "external_id",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            existing_nullable=True,
        )
