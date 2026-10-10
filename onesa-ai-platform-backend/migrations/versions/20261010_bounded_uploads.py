"""Durable owner-scoped file transport; keep the existing five MiB upload requirement."""

from alembic import op

revision = "20261010_uploads"
down_revision = "20261010_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE bounded_uploads (id uuid PRIMARY KEY, created_at timestamptz NOT NULL,
 user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 filename varchar(200) NOT NULL, media_type varchar(80) NOT NULL,
 size integer NOT NULL CHECK(size BETWEEN 1 AND 5242880), checksum varchar(64) NOT NULL,
 received integer NOT NULL CHECK(received BETWEEN 0 AND size),
 expires_at timestamptz NOT NULL, result jsonb);
CREATE INDEX ix_bounded_uploads_user_id ON bounded_uploads(user_id);
CREATE INDEX ix_bounded_uploads_expires_at ON bounded_uploads(expires_at);
CREATE TABLE upload_chunks (upload_id uuid REFERENCES bounded_uploads(id) ON DELETE CASCADE,
 sequence integer NOT NULL CHECK(sequence BETWEEN 0 AND 9),
 data bytea NOT NULL CHECK(octet_length(data) BETWEEN 1 AND 524288),
 PRIMARY KEY(upload_id,sequence));
""")


def downgrade() -> None:
    raise RuntimeError(
        "Review pending uploads and retention before any removal; use forward migrations"
    )
