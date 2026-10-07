"""Bind approved proposals to their exact executor, preserving existing claims.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("action_proposals", sa.Column("executor", sa.String(40), nullable=False, server_default="dry_run"))
    # Old live proposals were never tied to a specific adapter: require re-proposal.
    op.execute("UPDATE action_proposals SET executor = 'legacy_unbound' WHERE dry_run = false")


def downgrade():
    op.drop_column("action_proposals", "executor")
