"""Shared bounded model admission across API workers; no production policy is enabled here."""

from alembic import op

revision = "20261010_capacity"
down_revision = "20261010_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE model_leases (id uuid PRIMARY KEY, created_at timestamptz NOT NULL,
 user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at timestamptz NOT NULL);
CREATE INDEX ix_model_leases_user_id ON model_leases(user_id);
CREATE INDEX ix_model_leases_expires_at ON model_leases(expires_at);
""")


def downgrade() -> None:
    raise RuntimeError("Drain active leases and use an explicit forward rollback plan")
