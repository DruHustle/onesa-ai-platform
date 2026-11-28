"""Add native grants and sessions without changing existing browser authority."""

from alembic import op

revision = "20261128_native_sessions"
down_revision = "20261104_email_presentation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE native_sessions (
        session_id UUID PRIMARY KEY REFERENCES auth_sessions(id) ON DELETE CASCADE,
        token_hash VARCHAR(64) NOT NULL UNIQUE, platform VARCHAR(10) NOT NULL,
        CHECK (platform IN ('ios', 'android')))""")
    op.execute("""CREATE TABLE native_auth_requests (
        id UUID PRIMARY KEY, created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        platform VARCHAR(10) NOT NULL, code_challenge VARCHAR(43) NOT NULL,
        state VARCHAR(128) NOT NULL, expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        user_id UUID REFERENCES users(id) ON DELETE CASCADE,
        browser_session_id UUID REFERENCES auth_sessions(id) ON DELETE CASCADE,
        approved_at TIMESTAMP WITH TIME ZONE, code_hash VARCHAR(64) UNIQUE,
        code_expires_at TIMESTAMP WITH TIME ZONE, consumed_at TIMESTAMP WITH TIME ZONE,
        CHECK (platform IN ('ios', 'android')),
        CHECK ((user_id IS NULL) = (browser_session_id IS NULL)),
        CHECK ((code_hash IS NULL AND code_expires_at IS NULL AND approved_at IS NULL) OR
            (code_hash IS NOT NULL AND code_expires_at IS NOT NULL
             AND approved_at IS NOT NULL AND user_id IS NOT NULL)),
        CHECK (consumed_at IS NULL OR approved_at IS NOT NULL))""")
    op.execute(
        "CREATE INDEX ix_native_auth_requests_expires_at ON native_auth_requests(expires_at)"
    )


def downgrade() -> None:
    raise RuntimeError("Native sessions require an explicit forward rollback plan")
