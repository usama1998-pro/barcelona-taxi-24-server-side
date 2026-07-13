"""add pricing_passcode table

Revision ID: f7a1d4e5b6c7
Revises: e6f0c3d4a5b6
Create Date: 2026-07-13 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql


revision: str = "f7a1d4e5b6c7"
down_revision: Union[str, Sequence[str], None] = "e6f0c3d4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "pricing_passcode" not in tables:
        op.create_table(
            "pricing_passcode",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("code", sa.String(length=16), nullable=False),
            sa.Column("updated_at", mysql.DATETIME(fsp=3), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "pricing_passcode" in tables:
        op.drop_table("pricing_passcode")
