# Oracle VM architecture and troubleshooting

Classification: **protected engineering documentation**. Owner: Onesa operations.
Reviewed against the installed Oracle migration and read-only runtime evidence on
2026-10-16. Runtime health changes independently of source qualification; consult the
restricted current incident/release receipts before acting. This page contains no
credential values, private addresses, customer data or production backup contents.

## Architecture and responsibilities

The existing Frankfurt VM is displayed in Oracle as **Onesa UG Backend**. Its
previous display name was `onesa-portal-worker`; the 2026-10-16 rename changed only
the Console display name. Existing host identity, Tailscale identity, SSH shortcut
`onesa-portal-worker`, network and service names remain unchanged. It runs Ubuntu 24.04 on ARM64 with 1 OCPU, 6 GB RAM and a
50 GB boot volume. It hosts separate staging and production APIs, Portal background
workers, one shared private ClamAV scanner, and existing operations services.
Vercel continues to host the websites; Cloudflare Pages hosts protected engineering
Docs. Databases, Portal object storage, mail and AI inference remain external.
Migrating the API host did not move those datasets or install model weights on the VM.

Open [the interactive infrastructure layout](/architecture?diagram=infrastructure-current).
Its source is `docs/diagrams/infrastructure-current.mmd`; the protected diagram viewer
provides SVG/PNG/PDF exports. The same architecture is explained in the
[infrastructure reference](../ecosystem/INFRASTRUCTURE.md).

| Layer | Responsibility and boundary |
| --- | --- |
| Product frontends | Vercel serves Company/Portal, AI and Robot. Each server-side proxy uses only its own environment's API. Company public and Portal administration remain distinct hosts. |
| Public API ingress | One outbound Cloudflare Tunnel per environment; exact approved API hosts only, with an unmatched-host 404. Application sessions, authorization, CSRF and WAF remain enforced. |
| VM application runtime | Independent Docker Compose projects, loopback-only ports, separate staging/production networks, immutable ARM64 images, bounded CPU/memory and rotating logs. |
| Portal jobs and scanning | Separate staging/production workers share a private scanner Unix socket. Each worker retains its own database, object and mail configuration; the scanner has no public TCP listener. |
| Persistent data | Separate Portal/AI PostgreSQL targets and Robot Turso journals; Portal private object storage remains external. Local Robot storage volumes are environment-specific and are not permission or session recovery. |
| Operations | Existing systemd monitoring and encrypted-backup timers. Monitoring observes and alerts; it does not restart applications or repair data. |
| Administration | Approved owner PC → encrypted Tailscale overlay → pinned ordinary OpenSSH. This grants no application session. Retained restricted public SSH is a separate recovery path. |
| Other existing workloads | Existing BaSyx and unrelated VM services remain independently managed. This guide grants no authority to stop or reconfigure them. |

## Routing and service map

All host bindings below are **127.0.0.1**, reached by the matching local tunnel.
They are not public ports and must not be opened in OCI, the firewall or Tailscale.

| Product | Production API / host port | Staging API / host port | Liveness | Readiness |
| --- | --- | --- | --- | --- |
| Company Portal | `portal-api.onesa.eu` / 18300 | `portal-api-staging.onesa.eu` / 18301 | `/api/v1/health` | `/api/v1/ready` |
| AI Platform | `platform-api.onesa.eu` / 18000 | `platform-api-staging.onesa.eu` / 18001 | `/health` | `/core-ready`, `/ready` |
| AI Robot | `robot-api.onesa.eu` / 18431 | `robot-api-staging.onesa.eu` / 18432 | `/api/v1/health` | `/api/v1/ready` |

Container names follow `onesa-<portal|ai|robot>-oracle-api-<staging|production>-1`.
Portal workers are `onesa-portal-oracle-staging-worker-1` and
`onesa-portal-oracle-production-worker-1`; the shared scanner is
`onesa-portal-oracle-staging-scanner-1`. Product identity, public/protected access,
environment and Robot simulation/physical-controller state remain independent.

## Runtime files and resource controls

| Protected VM location | Purpose |
| --- | --- |
| `/opt/onesa/backends/<product>.yaml` | Installed Compose definitions, where product is `portal`, `ai` or `robot`. Compare to the owning repository's `compose.oracle-backend.yaml` and restricted installation receipt. |
| `/etc/onesa/backends/<product>-<environment>.env` | Existing environment-specific application configuration; root-owned mode 0600. Never print or copy into Docs/Actions. |
| `/etc/onesa/backends/<product>.images.env` | Immutable image IDs and actual source commits per environment. A desired tag is not deployed-source proof. |
| `/etc/onesa/backends/tunnel-<environment>.token` | Separate connector credential, root-only; systemd `LoadCredential` supplies it to the dynamic service user. |
| `/opt/onesa/portal-operations/` | Existing qualified monitor/backup component releases and active installation. Use its existing configuration and evidence, not a second monitoring stack. |
| `/var/lib/onesa/backend-application-release-20261016/` | Restricted application-release image archives, previous configuration and activation receipts for this release run. Not a general-purpose cleanup target. |

API memory caps: Portal staging/production 256/384 MiB; AI 384/512 MiB; Robot
192/256 MiB. Each staging API is limited to 0.25 CPU with lower shares; each production
API to 0.6 CPU with higher shares. The shared scanner has a 4 GiB cap and 0.8 CPU;
Portal staging/production workers have 768/512 MiB and 0.2/0.1 CPU respectively.
These are limits, not reservations: their sum exceeds host capacity. Low-traffic
acceptance does not establish simultaneous peak capacity. Observe actual memory,
CPU throttling, disk, queue age and latency; do not automatically resize, add swap or
purchase capacity. Builds and security scans run off the VM to avoid competing with
serving and scanning. Images are loaded by immutable ID after source/security checks.

## Read-only first response

Connect with the approved owner SSH shortcut; never disable host-key verification.
The following commands inspect selected fields and do not dump container environment
variables or production configuration. Run them inside the authorized VM session:

```sh
uptime
free -h
df -h /
sudo systemctl is-active docker tailscaled onesa-backend-tunnel@staging.service onesa-backend-tunnel@production.service
sudo systemctl list-timers onesa-portal-monitor.timer onesa-portal-backup.timer
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}'
sudo docker inspect --format '{{.Name}} image={{.Image}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} restarts={{.RestartCount}} oom={{.State.OOMKilled}} source={{index .Config.Labels "org.onesa.source-commit"}}' onesa-ai-oracle-api-production-1
curl --fail --max-time 10 http://127.0.0.1:18000/health
curl --fail --max-time 20 http://127.0.0.1:18000/core-ready
curl --fail --max-time 10 http://127.0.0.1:18431/api/v1/ready
```

Select the product/environment from the service map before substituting a container
or port. A failed `curl --fail` is a failed check, not permission to restart it.
Keep bounded logs and exact request times in restricted evidence. Do not paste raw
`docker inspect`, environment files, tunnel installation commands, cookies or logs
containing private requests into chat, Git or public troubleshooting pages.

## Diagnose the failing layer

| Symptom | Establish before changing anything | Smallest permitted next step |
| --- | --- | --- |
| Website works; API proxy returns 502/503 | Compare canonical proxy, exact external API host and VM loopback health. Check actual Vercel deployment and its server-side API binding. | Correct only a confirmed environment binding through the qualified release process. A Preview build pull does not prove runtime binding. |
| Cloudflare 502/1033 or connector unavailable | Loopback API health; corresponding `onesa-backend-tunnel@<environment>` status; bounded connector journal; exact-host routing and catch-all. | Restore only the intended reviewed connector/configuration after establishing its state. Keep tokens private; never create a blanket WAF/Access exception. |
| API liveness 200, readiness 503 | Read the sanitized readiness category and dependency identity; inspect scoped logs. Liveness proves only the process is alive. | Resolve the actual dependency/schema/lease problem. Never report the application accepted solely from `/health`. |
| AI 401/403 | Distinguish missing session, CSRF/Origin mismatch, invitation/access grant and foreign-object denial. Check the intended frontend/environment. | Use normal approved sign-in and exact-origin configuration. Do not weaken authorization or copy production sessions into tests. |
| AI generation or agent 503 | Separate provider/model availability, inference timeout, permission denial, application lease and provider quota using bounded diagnostics. | Use the existing approved diagnostic/qualification budget. No silent mock fallback, blind model switch or repeated paid inference. |
| Robot journal readiness 503 | Record fixed category/phase/transport/reconciliation fields, current source and lease state. Compare all existing seven-field history fingerprints using authorized read-only access. | Preserve stopped state and permission/controller boundaries. Prepare a qualified new-source correction if required; no old-source recovery restart, lease fencing, SQL repair or account reset. |
| Upload stays quarantined / scan fails | Scanner health, signature age, socket readiness, queue age, storage access and worker logs. | Keep the object quarantined; correct the actual scanner/storage issue. Never mark an upload clean manually or open a scanner TCP port. |
| Worker stops or mail is delayed | Correct environment, worker health, scanner readiness, exhausted retries and provider delivery receipt. | Investigate using the existing queue/runbook. Accepted mail is not proof of inbox delivery. Do not replay jobs blindly. |
| High latency, OOM or disk pressure | Compare per-container CPU/memory/restarts with host pressure, log growth and queue activity; distinguish database wake time from application rendering. | Stop unnecessary run-owned build/test load. Plan a reviewed resource correction; do not prune Docker/volumes, delete backups or restart unrelated services. |
| Monitor reports failure | Inspect the existing timer's actual sample, container health and alert delivery/clearance. | Fix the reported component and verify recovery. Do not disable the rule or run the installation bootstrap against populated production. |

### Observed Robot incident — 2026-10-16

At 11:00:16 UTC the production journal recorded `category=timeout`,
`phase=lease_renew`, `elapsed_ms=2001`, `transport_kind=ReadTimeout`,
`reconciliation=unavailable`. The container did not restart or report OOM;
liveness remained 200 while readiness returned 503. Read-only reconciliation
preserved all 76 production and 737 staging history fingerprints, found no pending
tasks, and verified unchanged production runtime configuration. The production
lease was expired; staging's lease was live. Underlying remote latency is not
established. This is an open readiness incident, not a successful deployment or
permission to restart the old source. Restricted current evidence owns subsequent
incident status; this dated observation is preserved.

## Deployment, rollback and evidence

Normal promotion is `dev → staging → main`; temporary reviewed security branches
are not environments. Existing GitHub-hosted PR jobs install/test without production
credentials. Owner-controlled release checks exact source, first-attempt CI/security,
immutable image, matching staging, preservation and the relevant attempt budget.
Build completion, a local timeout and provider failure are different states.
Reconcile accepted deployment IDs before any new request; retain receipts even on
failure. Local Oracle probes identify owner execution and actual CI separately;
they must never impersonate a GitHub Actions run or fabricate a trusted artifact.

Activate only the named qualified product/environment. Preserve the other APIs,
workers, scanner, databases, accounts, ingress protections and unrelated workloads.
No `compose down`, blanket restart, destructive Docker prune or automatic migration.
Record frontend deployment, actual backend image/source, readiness, protected access,
private denial and preservation independently. An unrelated service incident remains
reported; a successful AI deployment cannot mark Robot healthy.

Retain the previous qualified immutable image, exact frontend artifact and root-only
configuration. Roll back only after checking schema/compatibility and the approved
recovery procedure. Render is unavailable: restoring a historic Render URL does not
restore service. Robot lease/history recovery has its own stricter controls.

## Backups, alerts and access recovery

The existing Portal backup/monitor timers remain in service. Follow the owning
[backup reference](../database/BACKUP_RESTORE.md) and
[monitoring reference](../operations/MONITORING.md); retain existing encryption,
retention, keys and approved alert destination. Do not rerun an initial empty-database
restore fixture on populated production. AI's owner-approved 2026-10-16 snapshot
passed authenticated encryption/tamper checks and restore into one network-isolated
local container; the owned container and scratch volume were removed. That one-time
snapshot does not establish a new recurring AI backup service or an agreed RPO/RTO.
Production-data copies and destructive restores require their own scoped authority.

If Tailscale access fails, check local and VM device connectivity, approved peer
policy, `tailscaled`, pinned SSH and existing firewall rules. Use the retained
approved public SSH recovery path when available. Do not enable Funnel, Serve,
Tailscale SSH, exit/subnet routing, broad peer grants or new public ports to recover.
For loss of both SSH paths, use the established Oracle console recovery procedure;
Cloud Shell is a separate machine and does not bypass the host firewall.

## Further references

- [Application release and migration](DEPLOYMENT.md)
- [Private Tailscale administration](../operations/TAILSCALE_ADMINISTRATION.md)
- [Monitoring](../operations/MONITORING.md)
- [Recovery and restore](../operations/RECOVERY.md)
- [Infrastructure overview](../ecosystem/INFRASTRUCTURE.md)

Provider IDs, private addresses, tokens, exact runtime digests, data fingerprints and
backup/key locations remain in the existing restricted operator evidence, excluded
from public/internal site assets and search indexes.
