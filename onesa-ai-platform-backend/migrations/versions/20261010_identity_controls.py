"""Add opt-in invitation eligibility and durable password recovery without enabling them."""

from alembic import op

revision = "20261010_identity"
down_revision = "608f3f79f76e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE access_grants (user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 granted_at timestamptz NOT NULL, expires_at timestamptz NOT NULL);
CREATE TABLE identity_tokens (id uuid PRIMARY KEY, created_at timestamptz NOT NULL,
 purpose varchar(20) NOT NULL CHECK (purpose IN ('invitation', 'recovery')),
 email varchar(254) NOT NULL, user_id uuid REFERENCES users(id) ON DELETE CASCADE,
 token_hash varchar(64) NOT NULL UNIQUE, expires_at timestamptz NOT NULL,
 grant_expires_at timestamptz, consumed_at timestamptz, revoked_at timestamptz);
CREATE INDEX ix_identity_tokens_expires_at ON identity_tokens(expires_at);
CREATE TABLE identity_mail (token_id uuid PRIMARY KEY
 REFERENCES identity_tokens(id) ON DELETE CASCADE,
 state varchar(20) NOT NULL
 CHECK (state IN ('queued', 'leased', 'accepted', 'failed', 'cancelled')),
 attempts integer NOT NULL CHECK (attempts BETWEEN 0 AND 5), next_attempt_at timestamptz NOT NULL,
 lease_until timestamptz, lease_id uuid, provider_id varchar(200));
CREATE TABLE identity_audit (id uuid PRIMARY KEY, created_at timestamptz NOT NULL,
 actor_id uuid REFERENCES users(id) ON DELETE SET NULL, event varchar(40) NOT NULL, record_id uuid);
""")


def downgrade() -> None:
    raise RuntimeError(
        "Identity records require an explicit retention/recovery plan; use forward migrations"
    )
