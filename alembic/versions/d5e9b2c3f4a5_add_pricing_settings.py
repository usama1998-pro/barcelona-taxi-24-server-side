"""add pricing_settings table

Revision ID: d5e9b2c3f4a5
Revises: c4f8a1b2d3e4
Create Date: 2026-07-13 00:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql


revision: str = "d5e9b2c3f4a5"
down_revision: Union[str, Sequence[str], None] = "c4f8a1b2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "pricing_settings" not in tables:
        op.create_table(
            "pricing_settings",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("short_trip_max_km", sa.Float(), nullable=False),
            sa.Column("mid_max_km", sa.Float(), nullable=False),
            sa.Column("mid_rate_eur_per_km", sa.Float(), nullable=False),
            sa.Column("long_rate_eur_per_km", sa.Float(), nullable=False),
            sa.Column("infant_carrier_fare", sa.Integer(), nullable=False),
            sa.Column("updated_at", mysql.DATETIME(fsp=3), nullable=False),
        )
        op.execute(
            sa.text(
                """
                INSERT INTO pricing_settings (
                    id,
                    short_trip_max_km,
                    mid_max_km,
                    mid_rate_eur_per_km,
                    long_rate_eur_per_km,
                    infant_carrier_fare,
                    updated_at
                ) VALUES (
                    'default',
                    17,
                    32,
                    4,
                    2,
                    7,
                    UTC_TIMESTAMP(3)
                )
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "pricing_settings" in tables:
        op.drop_table("pricing_settings")
