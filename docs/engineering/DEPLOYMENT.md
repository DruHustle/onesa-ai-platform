# Independent application deployment

<!-- onesa-protected-source: ai-deployment -->

Detailed operational instructions are maintained in protected Engineering Docs.
This public source is a reference page, not a deployment or recovery runbook.

[Open the protected guide](https://docs.engineering.onesa.eu/docs/engineering/DEPLOYMENT).
Sign in through Onesa Portal with an individually approved engineering identity.

## Primary release path

Use the protected guide above for the maintained release procedure. This public
reference does not contain deployment targets, credentials or operational steps.

## Security releases and permanent branches

Keep `dev → staging → main` and temporary security-update branches. Review and
qualification remain mandatory; see the protected guide for authorized release work.

Public repository history may contain earlier editions; moving this active copy
does not erase historical exposure. Credentials, records and release evidence
belong in their existing restricted stores, never in this reference page.

## Oracle owner-run evidence bridge

The new `scripts/release/oracle_owner.py` adapter preserves owner-run receipts
with workflow run ID `0` and genuine CI run references. It requires a separately
commissioned, pinned external verifier and owner-controlled signing custody.
Repository code or an unsigned JSON file supplies no release authority.
The protected guide contains installation, qualification and recovery instructions;
source implementation alone does not establish commissioning or deployment.

The AI component runners, reviewed installer and credential-free prebuilt builder
now accompany the adapter. They keep candidate application bytes separate from
commissioned verification tools and record deployment intent before a provider
request. Source identity readback, additive-schema rollback, scoped synthetic
workflow checks and coordinated encrypted database/file recovery remain gates.
Their presence in source does not mean a host installation, qualification or
production deployment has completed. The protected evidence index records each
observed outcome separately.

The pinned uploader distinguishes a complete provider missing-file rejection from
an uncertain create response. Only the former permits one identical file-upload
continuation; lost, ambiguous or successful responses remain inspect-only.
Credential-free tests exercise the real pinned client against a loopback fixture.


The owner frontend runner binds and verifies the specifically named server API
origin independently of Git branch metadata. Manual prebuilt deployment must not
fall back to a loopback backend when branch-only variables are absent. The protected
guide contains the exact source-bound routing configuration and current records.
