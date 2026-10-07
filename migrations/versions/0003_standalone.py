"""Add product evidence and identity storage without rewriting historical claims.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("service_users", sa.Column("password_hash", sa.String(256), nullable=True))
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Backfill scope only; never invent incident/evidence content for historical runs.
    op.execute("""INSERT INTO tenants (id, name, created_at)
        SELECT tenant_id, tenant_id, CURRENT_TIMESTAMP FROM (
          SELECT tenant_id FROM service_users UNION SELECT tenant_id FROM ai_runs
          UNION SELECT tenant_id FROM action_proposals UNION SELECT tenant_id FROM action_audit
        ) AS old_tenants""")
    op.create_table(
        "bootstrap_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
    )
    op.execute("""INSERT INTO bootstrap_state (id, completed)
        SELECT 1, CASE WHEN EXISTS (SELECT 1 FROM service_users) THEN true ELSE false END""")
    op.create_table(
        "browser_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), sa.ForeignKey("service_users.id"), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_browser_sessions_user_id", "browser_sessions", ["user_id"])
    op.create_index("ix_browser_sessions_expires_at", "browser_sessions", ["expires_at"])
    op.create_table(
        "login_throttle",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ("evidence_events", "incidents"):
        op.create_table(
            name,
            sa.Column("id", sa.String(128), primary_key=True),
            sa.Column("tenant_id", sa.String(128), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("source_id", sa.String(128), nullable=False),
            sa.Column("external_id", sa.String(128), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "source_id", "external_id"),
            sa.UniqueConstraint("tenant_id", "id"),
        )
        op.create_index("ix_" + name + "_tenant_id", name, ["tenant_id"])
    op.create_table(
        "incident_events",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("incident_id", sa.String(128), primary_key=True),
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.ForeignKeyConstraint(["tenant_id", "incident_id"], ["incidents.tenant_id", "incidents.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "event_id"], ["evidence_events.tenant_id", "evidence_events.id"]),
    )
    op.create_table(
        "assets",
        sa.Column("tenant_id", sa.String(128), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("asset_id", sa.String(128), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade():
    # Explicit schema downgrade discards new-only data; backup required. Old claims survive.
    for name in (
        "assets",
        "incident_events",
        "incidents",
        "evidence_events",
        "login_throttle",
        "browser_sessions",
        "bootstrap_state",
        "tenants",
    ):
        op.drop_table(name)
    op.drop_column("service_users", "password_hash")
