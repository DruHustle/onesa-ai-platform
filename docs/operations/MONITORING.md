# Monitoring

`/health` is process liveness. `/ready` checks configured model health and required Alembic
revision, returning sanitized 503 when unavailable/incompatible. Compose uses DB readiness,
one-shot migration completion and API readiness before web startup. Embedding/provider
availability is reported by their feature errors; readiness does not claim those dependencies
have been qualified. API startup works without DB only for the documented skeleton probes.

`/metrics` requires `Authorization: Bearer ONESA_METRICS_TOKEN` and is not proxied by Next.js.
Prometheus counters label method/route-template/status; histograms measure time to response
headers, not complete stream duration. Python process metrics are also exposed. Keep scrape
credentials private on the internal network. No public metric port or scrape/alert deployment
has been configured.

Request logs are JSON containing event/request ID/method/route/status/duration, not prompts,
passwords, cookies or keys. Uvicorn raw access logging is disabled in containers. Correlation
IDs are generated locally. OpenTelemetry instrumentation is future work; no traces are claimed.

Generation counters record outcome/backend and histograms record full generation latency
and first-text timing separately from request-header timing. Labels contain no model URLs,
prompts or session identifiers. Actual reported token counts remain in owned persisted run/
assistant metadata; unknown counts are null. These local metrics do not imply alerts are deployed.

The split adds `onesa_dependency_available{dependency="model"|"database"}` based
on the latest readiness probe. Model and database checks fail closed independently;
a missing/unavailable configured model cannot produce a successful readiness result.
DB probes execute outside the event loop with connection/statement/overall deadlines.
Metrics initially have no dependency samples until the first readiness probe.
`infra/monitoring/prometheus.yaml` and `alerts.yaml` provide private bearer-file
scraping and backend/dependency/API-error/inference-failure rules. They require an
operator-managed metrics secret, deployment-specific retention, destinations and
alert delivery tests; no live Prometheus/GPU exporter/alert routing is claimed.
Monitor database/model-cache/backup filesystem usage on the target host as well.

## Executed acceptance 005 monitoring

The statements above about unconfigured deployment describe the earlier template. Acceptance
005 now runs isolated Prometheus and Alertmanager with private credential-file scrapes and an
authenticated local receiver. See `deployment/ACCEPTANCE_STAGING.md` and the acceptance report.
Actual backend, model-dependency and backup failures produced firing and resolved webhook
deliveries. External notification/on-call delivery and production monitoring remain pending.

`infra/monitoring/acceptance-alerts.yaml` uses five-second scrape/evaluation intervals,
15-second service/dependency/backup holds, backup age over two hourly intervals, a five-percent
API 5xx ratio held 30 seconds and backup-filesystem free space below ten percent held 30 seconds.
These short timings make local acceptance reproducible; select production windows after
traffic/on-call requirements are approved. The API histogram measures response headers;
full generation/first-text histograms measure inference separately. Authentication outcome,
agent outcome and planning-failure counters have bounded labels without email, UUID or prompt.
The worker exposes backup duration/failures/age/in-progress/files and filesystem capacity.
DB connectivity and model discovery follow readiness probes; discovery is not model generation.

Prometheus UI is http://localhost:9095, Alertmanager http://localhost:9096, worker on
loopback 9905. Only trusted local operators should access these consoles. The worker requires
its separate bearer token for status, backup trigger, metrics and alert delivery. Its receiver
stores alert name/status/time, discarding raw annotations and user content. Never publish these
ports, credentials or private status. No host/GPU exporter or full node capacity coverage is
claimed; Docker resource samples and native loaded-model memory supplement local tests.

For external routing, provision an approved receiver and private credential, change the
Alertmanager receiver under operator review, restrict egress, and provoke a controlled staging
failure. Observe actual destination delivery and resolution; record recipient/on-call ownership
without exposing the credential. Configuration alone does not qualify external alerting.

On service/model failure inspect readiness and aggregate metrics, restore the known endpoint
and verify a real authenticated generation. On backup failure check free space and restricted
backup login, trigger a new archive, restore it to a fresh database and compare fingerprints.
A resolved alert alone is not a data integrity check.
