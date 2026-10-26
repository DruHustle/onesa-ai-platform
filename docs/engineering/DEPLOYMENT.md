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
