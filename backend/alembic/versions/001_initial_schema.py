"""
Initial database schema for AutoTwin AI Phase 1

Revision ID: 001_initial
Revises: None
Create Date: 2026-01-15

============================================================================
Creates all tables required for Phase 1:
  - vehicles
  - vehicle_profiles
  - fault_events
  - timeline_events
  - health_snapshots
  - can_logs
  - scenarios
  - scenario_runs
  - system_config
============================================================================
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# ============================================================================
# REVISION IDENTIFIERS
# ============================================================================

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ============================================================================
# UPGRADE
# ============================================================================


def upgrade() -> None:
    """Create initial database schema."""

    # ------------------------------------------------------------------
    # Table: vehicles
    # ------------------------------------------------------------------
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("make", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(32), nullable=True),  # sedan, SUV, EV, truck
        sa.Column("engine_type", sa.String(64), nullable=True),
        sa.Column("transmission_type", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # Table: vehicle_profiles
    # ------------------------------------------------------------------
    op.create_table(
        "vehicle_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dbc_path", sa.String(256), nullable=True),
        sa.Column("fault_rules_path", sa.String(256), nullable=True),
        sa.Column("model_3d_path", sa.String(256), nullable=True),
        sa.Column("dashboard_layout", sa.Text(), nullable=True),  # JSON
        sa.Column("subsystem_map", sa.Text(), nullable=True),     # JSON
        sa.Column("signal_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # Table: fault_events
    # ------------------------------------------------------------------
    op.create_table(
        "fault_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fault_id", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rule_id", sa.String(64), nullable=False, index=True),
        sa.Column("severity", sa.String(16), nullable=False, index=True),  # INFO, LOW, MEDIUM, HIGH, CRITICAL
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("message", sa.String(512), nullable=False),
        sa.Column("signal_values", sa.Text(), nullable=True),       # JSON
        sa.Column("possible_causes", sa.Text(), nullable=True),     # JSON array
        sa.Column("recommendation", sa.String(512), nullable=True),
        sa.Column("estimated_repair_time", sa.String(64), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("subsystem", sa.String(32), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), default=False, nullable=False),
        sa.Column("resolved", sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
    )

    # ------------------------------------------------------------------
    # Table: timeline_events
    # ------------------------------------------------------------------
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False, index=True),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column("message", sa.String(512), nullable=False),
        sa.Column("signal_name", sa.String(64), nullable=True),
        sa.Column("signal_value", sa.Float(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),  # JSON
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
    )

    # ------------------------------------------------------------------
    # Table: health_snapshots
    # ------------------------------------------------------------------
    op.create_table(
        "health_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("engine_score", sa.Float(), nullable=True),
        sa.Column("battery_score", sa.Float(), nullable=True),
        sa.Column("brake_score", sa.Float(), nullable=True),
        sa.Column("cooling_score", sa.Float(), nullable=True),
        sa.Column("transmission_score", sa.Float(), nullable=True),
        sa.Column("electrical_score", sa.Float(), nullable=True),
        sa.Column("active_fault_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
    )

    # ------------------------------------------------------------------
    # Table: can_logs
    # ------------------------------------------------------------------
    op.create_table(
        "can_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=False, index=True),
        sa.Column("can_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=True),
        sa.Column("dlc", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(2), nullable=True),  # RX or TX
        sa.Column("timestamp_us", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # Table: scenarios
    # ------------------------------------------------------------------
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("category", sa.String(32), nullable=True),  # normal, fault, stress
        sa.Column("definition", sa.Text(), nullable=True),     # JSON
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # Table: scenario_runs
    # ------------------------------------------------------------------
    op.create_table(
        "scenario_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.String(64), unique=True, nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(16), default="running", nullable=False),  # running, completed, aborted
        sa.Column("fault_count", sa.Integer(), default=0),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # ------------------------------------------------------------------
    # Table: system_config
    # ------------------------------------------------------------------
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # Indexes (additional performance indexes)
    # ------------------------------------------------------------------
    op.create_index("ix_fault_events_vehicle_severity", "fault_events", ["vehicle_id", "severity"])
    op.create_index("ix_fault_events_resolved_created", "fault_events", ["resolved", "created_at"])
    op.create_index("ix_timeline_vehicle_created", "timeline_events", ["vehicle_id", "created_at"])
    op.create_index("ix_health_vehicle_created", "health_snapshots", ["vehicle_id", "created_at"])
    op.create_index("ix_can_logs_session_timestamp", "can_logs", ["session_id", "timestamp_us"])

    # ------------------------------------------------------------------
    # Seed data: Default system configuration
    # ------------------------------------------------------------------
    op.execute("""
        INSERT INTO system_config (key, value, description) VALUES
        ('broadcast_interval_ms', '50', 'WebSocket broadcast interval in milliseconds'),
        ('fault_cooldown_s', '30', 'Seconds before a fault can re-trigger'),
        ('health_update_interval_s', '10', 'Health score recalculation interval'),
        ('timeline_max_events', '10000', 'Maximum timeline events to retain'),
        ('can_timeout_ms', '2000', 'CAN data timeout threshold'),
        ('serial_baud_rate', '115200', 'Serial port baud rate'),
        ('app_version', '1.0.0', 'Application version'),
        ('schema_version', '001_initial', 'Database schema version')
    """)


# ============================================================================
# DOWNGRADE
# ============================================================================


def downgrade() -> None:
    """Drop all tables (reverse of upgrade)."""
    op.drop_table("system_config")
    op.drop_table("scenario_runs")
    op.drop_table("scenarios")
    op.drop_table("can_logs")
    op.drop_table("health_snapshots")
    op.drop_table("timeline_events")
    op.drop_table("fault_events")
    op.drop_table("vehicle_profiles")
    op.drop_table("vehicles")