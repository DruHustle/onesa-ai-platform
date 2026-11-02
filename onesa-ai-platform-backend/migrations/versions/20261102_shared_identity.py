"""Add shared Onesa identity without changing native users or existing owned records."""

from alembic import op

revision = "20261102_shared_identity"
down_revision = "20261026_cybersecurity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE identity_sessions (
        session_id UUID PRIMARY KEY REFERENCES auth_sessions(id) ON DELETE CASCADE,
        issuer VARCHAR(1000) NOT NULL, subject VARCHAR(36) NOT NULL,
        encrypted_token VARCHAR(8192) NOT NULL)""")
    op.execute("""CREATE TABLE shared_identities (
        id UUID PRIMARY KEY, created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        issuer VARCHAR(1000) NOT NULL, subject VARCHAR(36) NOT NULL,
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(issuer, subject))""")
    op.execute("""CREATE TABLE identity_transactions (
        state_hash VARCHAR(64) PRIMARY KEY, browser_hash VARCHAR(64) NOT NULL,
        payload VARCHAR(16384) NOT NULL, expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        consumed_at TIMESTAMP WITH TIME ZONE)""")
    op.execute(
        "CREATE INDEX ix_identity_transactions_expires_at ON identity_transactions(expires_at)"
    )


def downgrade() -> None:
    raise RuntimeError("Shared identities require an explicit forward rollback plan")
