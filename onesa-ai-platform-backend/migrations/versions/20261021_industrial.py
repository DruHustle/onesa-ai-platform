"""Add owner-scoped synthetic investigations; no existing record is modified."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261021_industrial"
down_revision = "20261010_capacity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industrial_investigations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("revision > 0"),
        sa.CheckConstraint("status IN ('ready', 'running', 'completed', 'failed', 'cancelled')"),
    )
    op.create_index(
        "ix_industrial_investigations_user_id", "industrial_investigations", ["user_id"]
    )


def downgrade() -> None:
    raise RuntimeError("Preserve saved investigations; use an explicit forward rollback plan")
