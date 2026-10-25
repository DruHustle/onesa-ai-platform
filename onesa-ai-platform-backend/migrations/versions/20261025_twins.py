"""Add owned twins and evidence; preserve existing records and original files."""

from alembic import op

revision = "20261025_twins"
down_revision = "20261021_industrial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE twin_files (
    filename VARCHAR(200) NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    size INTEGER NOT NULL, 
    details JSONB NOT NULL, 
    user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CHECK (size BETWEEN 1 AND 4194304), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_twin_files_user_id ON twin_files (user_id)")
    op.execute(
        """CREATE TABLE twin_templates (
    name VARCHAR(120) NOT NULL, 
    kind VARCHAR(80) NOT NULL, 
    definition JSONB NOT NULL, 
    user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_twin_templates_user_id ON twin_templates (user_id)")
    op.execute(
        """CREATE TABLE twin_assets (
    template_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    serial VARCHAR(120) NOT NULL, 
    definition JSONB NOT NULL, 
    active_model_id UUID, 
    revision INTEGER NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CHECK (revision > 0), 
    UNIQUE (user_id, serial), 
    FOREIGN KEY(template_id) REFERENCES twin_templates (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_twin_assets_user_id ON twin_assets (user_id)")
    op.execute(
        """CREATE TABLE twin_models (
    template_id UUID NOT NULL, 
    file_id UUID NOT NULL, 
    definition JSONB NOT NULL, 
    user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(template_id) REFERENCES twin_templates (id), 
    FOREIGN KEY(file_id) REFERENCES twin_files (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_twin_models_user_id ON twin_models (user_id)")
    op.execute(
        """CREATE TABLE twin_notes (
    asset_id UUID NOT NULL, 
    component_id UUID, 
    kind VARCHAR(20) NOT NULL, 
    payload JSONB NOT NULL, 
    user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CHECK (kind IN ('annotation', 'viewpoint', 'inspection')), 
    FOREIGN KEY(asset_id) REFERENCES twin_assets (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_twin_notes_user_id ON twin_notes (user_id)")
    op.execute(
        """CREATE TABLE twin_sources (
    asset_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    definition JSONB NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    last_seen_at TIMESTAMP WITH TIME ZONE, 
    user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(asset_id) REFERENCES twin_assets (id) ON DELETE CASCADE, 
    UNIQUE (token_hash), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_twin_sources_user_id ON twin_sources (user_id)")
    op.execute(
        """CREATE TABLE twin_readings (
    source_id UUID NOT NULL, 
    asset_id UUID NOT NULL, 
    component_id UUID NOT NULL, 
    message_id VARCHAR(160) NOT NULL, 
    tag VARCHAR(80) NOT NULL, 
    mode VARCHAR(16) NOT NULL, 
    unit VARCHAR(24) NOT NULL, 
    value FLOAT NOT NULL, 
    quality VARCHAR(16) NOT NULL, 
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    provenance JSONB NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (source_id, message_id, tag, mode), 
    CHECK (mode IN ('live', 'simulated', 'replay')), 
    CHECK (quality IN ('good', 'bad', 'unknown')), 
    FOREIGN KEY(source_id) REFERENCES twin_sources (id) ON DELETE CASCADE, 
    FOREIGN KEY(asset_id) REFERENCES twin_assets (id) ON DELETE CASCADE
)"""
    )
    op.execute(
        "CREATE INDEX ix_twin_readings_history ON twin_readings (asset_id, mode, observed_at, id)"
    )
    op.execute(
        """CREATE TABLE twin_events (
    asset_id UUID NOT NULL, 
    source_id UUID NOT NULL, 
    component_id UUID NOT NULL, 
    reading_id UUID NOT NULL, 
    details JSONB NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(asset_id) REFERENCES twin_assets (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_id) REFERENCES twin_sources (id) ON DELETE CASCADE, 
    FOREIGN KEY(reading_id) REFERENCES twin_readings (id) ON DELETE CASCADE
)"""
    )
    op.execute("CREATE INDEX ix_twin_events_asset_id ON twin_events (asset_id, created_at)")


def downgrade() -> None:
    raise RuntimeError(
        "Preserve equipment, original files and history; use an explicit forward rollback plan"
    )
