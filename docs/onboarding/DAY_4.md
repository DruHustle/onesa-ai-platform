# Day 4 — Understand operations

Open the [interactive Day 4 workflow](/onboarding#day-4). Source: `docs/diagrams/day-four.mmd`; SVG/PNG/PDF exports are available from the diagram viewer. Reviewed 2026-10-13; distinguish implementation from hosted acceptance.

## Learning objectives

- Read health and scanner status without revealing secrets.
- Locate monitoring backup restore and incident runbooks.
- Identify operational evidence still missing.

## Practical checkpoints

- [ ] Use ssh -O check onesa-portal-worker from authorized owner setup.
- [ ] Inspect only redacted status; never compose config without --quiet.
- [ ] Identify the isolated restore command and on-call owner escalation path.

## Detailed references

- [Monitoring](/docs/operations/MONITORING)
- [Incident Response](/docs/operations/INCIDENT_RESPONSE)
- [Backup Restore](/docs/database/BACKUP_RESTORE)
- [Operations](/docs/ecosystem/OPERATIONS)

## Read-only owner diagnostics

With the authorized existing SSH setup: `ssh -O check onesa-portal-worker` and `ssh onesa-portal-worker`. Follow the Portal Oracle runtime runbook for `docker compose ... ps`, `config --quiet`, scanner PONG and the worker's health command. Do not print container environment, connection strings or private applicant files. Health does not prove mail delivery or restored backups.

Keep production legacy worker processing available until its qualified replacement is operational. Database binding, bucket access and actual synthetic data provenance must pass independently. Recovery restores go to isolated targets; production overwrite needs separate destructive-operation authorization.
