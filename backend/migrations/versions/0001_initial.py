"""Schema awal tabel aplikasi WSNova.

Revision ID: 0001_initial
Revises: None
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_type():
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _json_type():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "control_config",
        sa.Column("config_version", sa.String(length=50), nullable=False),
        sa.Column("membership_params", _json_type(), nullable=False),
        sa.Column("rule_base", _json_type(), nullable=False),
        sa.Column("dust_low_reference", sa.Float(), nullable=False),
        sa.Column("dust_high_reference", sa.Float(), nullable=False),
        sa.Column("u_off", sa.Float(), nullable=False),
        sa.Column("u_max", sa.Float(), nullable=False),
        sa.Column("d_min", sa.Float(), nullable=False),
        sa.Column("delta_d_update", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("config_version"),
    )

    op.create_table(
        "zone_nodes",
        sa.Column("zone_node_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("zone_id", sa.String(length=50), nullable=False),
        sa.Column("node_id", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("zone_node_id"),
        sa.UniqueConstraint("zone_id", "node_id", name="uq_zone_node"),
    )
    op.create_index("ix_zone_nodes_zone_node_id", "zone_nodes", ["zone_node_id"], unique=False)

    op.create_table(
        "mock_receiver_valid_data",
        sa.Column("id", _id_type(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.String(length=50), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Float(), nullable=False),
        sa.Column("dust_raw_voltage", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status_valid", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mock_receiver_valid_data_id", "mock_receiver_valid_data", ["id"], unique=False)
    op.create_index("ix_mock_receiver_valid_data_node_id", "mock_receiver_valid_data", ["node_id"], unique=False)

    op.create_table(
        "fuzzy_results",
        sa.Column("fuzzy_result_id", _id_type(), autoincrement=True, nullable=False),
        sa.Column("zone_node_id", sa.Integer(), nullable=False),
        sa.Column("config_version", sa.String(length=50), nullable=False),
        sa.Column("processing_cycle_id", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.BigInteger(), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("humidity", sa.Float(), nullable=True),
        sa.Column("dust_raw_voltage", sa.Float(), nullable=True),
        sa.Column("dust_index", sa.Float(), nullable=False),
        sa.Column("condition_score", sa.Float(), nullable=False),
        sa.Column("condition_class", sa.String(length=50), nullable=False),
        sa.Column("control_level", sa.Float(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["config_version"], ["control_config.config_version"]),
        sa.ForeignKeyConstraint(["zone_node_id"], ["zone_nodes.zone_node_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("fuzzy_result_id"),
        sa.UniqueConstraint(
            "zone_node_id", "source_record_id", "config_version",
            name="uq_fuzzy_node_record_cfg",
        ),
    )
    op.create_index("ix_fuzzy_results_fuzzy_result_id", "fuzzy_results", ["fuzzy_result_id"], unique=False)
    op.create_index("ix_fuzzy_results_processing_cycle_id", "fuzzy_results", ["processing_cycle_id"], unique=False)

    op.create_table(
        "zone_controls",
        sa.Column("zone_control_id", _id_type(), autoincrement=True, nullable=False),
        sa.Column("config_version", sa.String(length=50), nullable=False),
        sa.Column("processing_cycle_id", sa.String(length=100), nullable=False),
        sa.Column("zone_id", sa.String(length=50), nullable=False),
        sa.Column("control_fuzzy_result_id", sa.BigInteger(), nullable=True),
        sa.Column("control_node_id", sa.String(length=50), nullable=True),
        sa.Column("zone_control_level", sa.Float(), nullable=True),
        sa.Column("pwm_command_percent", sa.Float(), nullable=False),
        sa.Column("candidate_pwm_percent", sa.Float(), nullable=True),
        sa.Column("previous_pwm_percent", sa.Float(), nullable=True),
        sa.Column("auto_pwm_percent", sa.Float(), nullable=True),
        sa.Column("hysteresis_held", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("control_status", sa.String(length=50), nullable=False),
        sa.Column("fan_command_status", sa.String(length=50), nullable=False),
        sa.Column("control_mode", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["config_version"], ["control_config.config_version"]),
        sa.ForeignKeyConstraint(
            ["control_fuzzy_result_id"], ["fuzzy_results.fuzzy_result_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("zone_control_id"),
    )
    op.create_index("ix_zone_controls_processing_cycle_id", "zone_controls", ["processing_cycle_id"], unique=False)
    op.create_index("ix_zone_controls_zone_control_id", "zone_controls", ["zone_control_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_zone_controls_zone_control_id", table_name="zone_controls")
    op.drop_index("ix_zone_controls_processing_cycle_id", table_name="zone_controls")
    op.drop_table("zone_controls")
    op.drop_index("ix_fuzzy_results_processing_cycle_id", table_name="fuzzy_results")
    op.drop_index("ix_fuzzy_results_fuzzy_result_id", table_name="fuzzy_results")
    op.drop_table("fuzzy_results")
    op.drop_index("ix_mock_receiver_valid_data_node_id", table_name="mock_receiver_valid_data")
    op.drop_index("ix_mock_receiver_valid_data_id", table_name="mock_receiver_valid_data")
    op.drop_table("mock_receiver_valid_data")
    op.drop_index("ix_zone_nodes_zone_node_id", table_name="zone_nodes")
    op.drop_table("zone_nodes")
    op.drop_table("control_config")
