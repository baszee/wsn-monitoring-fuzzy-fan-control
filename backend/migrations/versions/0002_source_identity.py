"""Tambahkan identitas sumber pada hasil fuzzy.

Revision ID: 0002_source_identity
Revises: 0001_initial
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_source_identity"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fuzzy_results",
        sa.Column("source_name", sa.String(length=32), nullable=True),
    )
    op.execute(sa.text("UPDATE fuzzy_results SET source_name = 'legacy' WHERE source_name IS NULL"))

    with op.batch_alter_table("fuzzy_results") as batch_op:
        batch_op.alter_column(
            "source_name", existing_type=sa.String(length=32), nullable=False
        )
        batch_op.drop_constraint("uq_fuzzy_node_record_cfg", type_="unique")
        batch_op.create_unique_constraint(
            "uq_fuzzy_source_node_record_cfg",
            ["source_name", "zone_node_id", "source_record_id", "config_version"],
        )


def downgrade() -> None:
    with op.batch_alter_table("fuzzy_results") as batch_op:
        batch_op.drop_constraint("uq_fuzzy_source_node_record_cfg", type_="unique")
        batch_op.create_unique_constraint(
            "uq_fuzzy_node_record_cfg",
            ["zone_node_id", "source_record_id", "config_version"],
        )
        batch_op.drop_column("source_name")
