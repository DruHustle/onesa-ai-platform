# Incident response

Record timestamps/correlation IDs and affected service/features without copying private
prompts/tokens into public tickets. Preserve protected logs and a backup when safe. Assess
whether the failure is auth/ownership, storage/migration, serving, upload parsing or resource
exhaustion. Disable affected ingress/feature on the configured operator host if necessary;
do not publish credentials or destroy the database to recover availability.

For credential exposure rotate relevant secrets and revoke sessions; for ownership issues
isolate the affected route and audit evidence; for serving failures restore the known-good
model configuration. Validate restored data and authorized smoke workflows before reopening.
Record cause, measured impact, corrective tests and documentation changes. No external paging,
notification integration, incident SLA or response team has been configured in this repo.

Acceptance 005 now verifies local alert delivery and resolution for backend/model/backup
failures. External paging, named responders, notification duties and response targets remain
unapproved. Use the monitoring/recovery procedures above before reopening affected routes;
record incident timestamps and request IDs, not private prompts, document text or credentials.
