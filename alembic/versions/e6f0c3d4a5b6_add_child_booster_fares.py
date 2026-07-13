"""add child seat and booster fares to pricing_settings

Revision ID: e6f0c3d4a5b6
Revises: d5e9b2c3f4a5
Create Date: 2026-07-13 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "e6f0c3d4a5b6"
down_revision: Union[str, Sequence[str], None] = "d5e9b2c3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("pricing_settings")}
    if "child_seat_fare" not in columns:
        op.add_column(
            "pricing_settings",
            sa.Column("child_seat_fare", sa.Integer(), nullable=False, server_default="7"),
        )
        op.alter_column("pricing_settings", "child_seat_fare", server_default=None)
    if "booster_fare" not in columns:
        op.add_column(
            "pricing_settings",
            sa.Column("booster_fare", sa.Integer(), nullable=False, server_default="7"),
        )
        op.alter_column("pricing_settings", "booster_fare", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("pricing_settings")}
    if "booster_fare" in columns:
        op.drop_column("pricing_settings", "booster_fare")
    if "child_seat_fare" in columns:
        op.drop_column("pricing_settings", "child_seat_fare")
