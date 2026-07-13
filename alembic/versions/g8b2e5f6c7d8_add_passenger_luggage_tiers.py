"""add passenger/luggage rate tiers to pricing_settings

Revision ID: g8b2e5f6c7d8
Revises: f7a1d4e5b6c7
Create Date: 2026-07-13 22:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "g8b2e5f6c7d8"
down_revision: Union[str, Sequence[str], None] = "f7a1d4e5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TIERS_JSON = (
    '[{"passengers":1,"luggage":1,"price":52},'
    '{"passengers":2,"luggage":2,"price":52},'
    '{"passengers":3,"luggage":3,"price":57},'
    '{"passengers":4,"luggage":4,"price":62},'
    '{"passengers":5,"luggage":5,"price":72},'
    '{"passengers":6,"luggage":6,"price":77},'
    '{"passengers":7,"luggage":7,"price":84},'
    '{"passengers":8,"luggage":8,"price":110},'
    '{"passengers":8,"luggage":12,"price":127},'
    '{"passengers":8,"luggage":16,"price":153}]'
)


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("pricing_settings")}
    if "passenger_luggage_tiers" not in columns:
        op.add_column(
            "pricing_settings",
            sa.Column("passenger_luggage_tiers", sa.JSON(), nullable=True),
        )
        op.execute(
            sa.text(
                "UPDATE pricing_settings "
                f"SET passenger_luggage_tiers = CAST(:tiers AS JSON)"
            ).bindparams(tiers=DEFAULT_TIERS_JSON)
        )
        op.alter_column(
            "pricing_settings",
            "passenger_luggage_tiers",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("pricing_settings")}
    if "passenger_luggage_tiers" in columns:
        op.drop_column("pricing_settings", "passenger_luggage_tiers")
