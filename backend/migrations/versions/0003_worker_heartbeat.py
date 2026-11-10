"""Tabel detak worker untuk instance tampilan.

Revision ID: 0003_worker_heartbeat
Revises: 0002_source_identity
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_worker_heartbeat"
down_revision: Union[str, Sequence[str], None] = "0002_source_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(length=32), primary_key=True),
        sa.Column("last_cycle_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_source_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=128), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_mode", sa.String(length=32), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeats")
