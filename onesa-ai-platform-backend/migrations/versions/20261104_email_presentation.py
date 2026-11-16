"""Keep HTML mail attempts distinct from legacy plain-only workers on rollback."""

from alembic import op

revision = "20261104_email_presentation"
down_revision = "20261102_shared_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("identity_mail_state_check", "identity_mail", type_="check")
    op.create_check_constraint(
        "identity_mail_state_check",
        "identity_mail",
        "state IN ('queued', 'leased', 'queued_html_v1', 'leased_html_v1', "
        "'accepted', 'failed', 'cancelled')",
    )


def downgrade() -> None:
    raise RuntimeError("Retain versioned delivery states; use an explicit forward rollback plan")
