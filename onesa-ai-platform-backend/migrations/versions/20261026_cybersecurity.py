"""Add independent security evidence and decisions; no existing data is changed."""

from alembic import op

revision = "20261026_cybersecurity"
down_revision = "20261025_twins"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE cyber_assets (
        name VARCHAR(120) NOT NULL,
        identity VARCHAR(128) NOT NULL,
        zone VARCHAR(80) NOT NULL,
        criticality VARCHAR(16) NOT NULL,
        details JSONB NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (user_id, identity),
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_assets_user_id ON cyber_assets (user_id)")
    op.execute(
        """CREATE TABLE cyber_sources (
        name VARCHAR(120) NOT NULL,
        namespace VARCHAR(64) NOT NULL,
        token_hash VARCHAR(64),
        scope VARCHAR(16) NOT NULL,
        config JSONB NOT NULL,
        revoked_at TIMESTAMP WITH TIME ZONE,
        last_seen_at TIMESTAMP WITH TIME ZONE,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (user_id, namespace),
        UNIQUE (token_hash),
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_sources_user_id ON cyber_sources (user_id)")
    op.execute(
        """CREATE TABLE cyber_baselines (
        source_id UUID NOT NULL,
        revision VARCHAR(128) NOT NULL,
        config JSONB NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (source_id, revision),
        FOREIGN KEY(source_id) REFERENCES cyber_sources (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_baselines_user_id ON cyber_baselines (user_id)")
    op.execute(
        """CREATE TABLE cyber_findings (
        source_id UUID NOT NULL,
        asset_id UUID,
        dedupe_key VARCHAR(64) NOT NULL,
        rule VARCHAR(64) NOT NULL,
        rule_version VARCHAR(32) NOT NULL,
        mode VARCHAR(16) NOT NULL,
        run_id VARCHAR(128) NOT NULL,
        severity VARCHAR(16) NOT NULL,
        confidence VARCHAR(16) NOT NULL,
        priority INTEGER NOT NULL,
        first_seen TIMESTAMP WITH TIME ZONE NOT NULL,
        last_seen TIMESTAMP WITH TIME ZONE NOT NULL,
        occurrences INTEGER NOT NULL,
        details JSONB NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(source_id) REFERENCES cyber_sources (id) ON DELETE CASCADE,
        FOREIGN KEY(asset_id) REFERENCES cyber_assets (id) ON DELETE CASCADE,
        UNIQUE (dedupe_key),
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_findings_user_id ON cyber_findings (user_id)")
    op.execute(
        """CREATE TABLE cyber_mappings (
        source_id UUID NOT NULL,
        asset_id UUID NOT NULL,
        external_namespace VARCHAR(128) NOT NULL,
        external_asset VARCHAR(128) NOT NULL,
        external_component VARCHAR(128) NOT NULL,
        review JSONB NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (source_id, external_namespace, external_asset, external_component),
        FOREIGN KEY(source_id) REFERENCES cyber_sources (id) ON DELETE CASCADE,
        FOREIGN KEY(asset_id) REFERENCES cyber_assets (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_mappings_user_id ON cyber_mappings (user_id)")
    op.execute(
        """CREATE TABLE cyber_policies (
        source_id UUID NOT NULL,
        version INTEGER NOT NULL,
        config JSONB NOT NULL,
        sha256 VARCHAR(64) NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (source_id, version),
        FOREIGN KEY(source_id) REFERENCES cyber_sources (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_policies_user_id ON cyber_policies (user_id)")
    op.execute(
        """CREATE TABLE cyber_reports (
        asset_id UUID NOT NULL,
        sha256 VARCHAR(64) NOT NULL,
        profile VARCHAR(48) NOT NULL,
        producer VARCHAR(160) NOT NULL,
        details JSONB NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(asset_id) REFERENCES cyber_assets (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_reports_user_id ON cyber_reports (user_id)")
    op.execute(
        """CREATE TABLE cyber_events (
        source_id UUID NOT NULL,
        source_event_id VARCHAR(128) NOT NULL,
        asset_id UUID,
        mapping_id UUID,
        event_type VARCHAR(64) NOT NULL,
        mode VARCHAR(16) NOT NULL,
        run_id VARCHAR(128) NOT NULL,
        occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        sha256 VARCHAR(64) NOT NULL,
        wire JSONB NOT NULL,
        provenance JSONB NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (source_id, source_event_id),
        FOREIGN KEY(source_id) REFERENCES cyber_sources (id) ON DELETE CASCADE,
        FOREIGN KEY(asset_id) REFERENCES cyber_assets (id) ON DELETE CASCADE,
        FOREIGN KEY(mapping_id) REFERENCES cyber_mappings (id),
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_events_owner_time ON cyber_events (user_id, created_at, id)")
    op.execute("CREATE INDEX ix_cyber_events_user_id ON cyber_events (user_id)")
    op.execute(
        """CREATE INDEX ix_cyber_events_window ON cyber_events (source_id, mode, run_id, event_type,
occurred_at)"""
    )
    op.execute(
        """CREATE TABLE cyber_investigations (
        title VARCHAR(160) NOT NULL,
        finding_id UUID NOT NULL,
        status VARCHAR(24) NOT NULL,
        priority INTEGER NOT NULL,
        revision INTEGER NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
        acceptance_until TIMESTAMP WITH TIME ZONE,
        snapshot JSONB NOT NULL,
        sha256 VARCHAR(64) NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(finding_id) REFERENCES cyber_findings (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_investigations_user_id ON cyber_investigations (user_id)")
    op.execute(
        """CREATE TABLE cyber_results (
        finding_id UUID NOT NULL,
        evidence_key VARCHAR(64) NOT NULL,
        snapshot JSONB NOT NULL,
        sha256 VARCHAR(64) NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (finding_id, evidence_key),
        FOREIGN KEY(finding_id) REFERENCES cyber_findings (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_results_user_id ON cyber_results (user_id)")
    op.execute(
        """CREATE TABLE cyber_actions (
        investigation_id UUID,
        kind VARCHAR(48) NOT NULL,
        details JSONB NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(investigation_id) REFERENCES cyber_investigations (id) ON DELETE
CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_actions_user_id ON cyber_actions (user_id)")
    op.execute(
        """CREATE TABLE cyber_summaries (
        investigation_id UUID NOT NULL,
        snapshot JSONB NOT NULL,
        sha256 VARCHAR(64) NOT NULL,
        result JSONB NOT NULL,
        user_id UUID NOT NULL,
        sensitive BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(investigation_id) REFERENCES cyber_investigations (id) ON DELETE
CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_cyber_summaries_user_id ON cyber_summaries (user_id)")


def downgrade() -> None:
    raise RuntimeError(
        "Preserve security evidence and decisions; use an explicit forward rollback plan"
    )
