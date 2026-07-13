"""add driver_list_label to Booking

Revision ID: c4f8a1b2d3e4
Revises: aa7e98586fd7
Create Date: 2026-07-12 22:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c4f8a1b2d3e4"
down_revision: Union[str, Sequence[str], None] = "aa7e98586fd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("Booking")}
    if "driver_list_label" not in columns:
        op.add_column(
            "Booking",
            sa.Column("driver_list_label", sa.String(length=48), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("Booking")}
    if "driver_list_label" in columns:
        op.drop_column("Booking", "driver_list_label")
