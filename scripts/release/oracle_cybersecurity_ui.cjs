// Owner-run observations, never authorization. Only the separately pinned runner
// may feed these results into the external signed release ledger.
process.on('uncaughtException', () => {
  console.error('Oracle cybersecurity probe refused; inspect private receipt.');
  process.exitCode = 1;
});
const fs = require('node:fs'), path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '../..');
const {chromium, expect} = createRequire(path.join(root, 'onesa-ai-platform-frontend/apps/chat/package.json'))('@playwright/test');
function need(value, code) { if (!value) throw Error(code); }
function privateJSON(file) {
  const s = fs.lstatSync(file);
  need(s.isFile() && !s.isSymbolicLink() && !(s.mode & 0o077) && s.uid === process.getuid() && s.size < 16384, 'PRIVATE_PROBE_CONTEXT');
  return JSON.parse(fs.readFileSync(file));
}
const ctx = privateJSON(process.env.ONESA_ORACLE_CYBERSECURITY_CONTEXT);
const origin = new URL(ctx.origin).origin;
const local = ['127.0.0.1', 'localhost', '[::1]'].includes(new URL(origin).hostname);
need((ctx.environment === 'staging' && /^https:\/\/onesa-ai-platform-[a-z0-9-]+\.vercel\.app$/.test(origin)) ||
  (ctx.environment === 'production' && origin === 'https://platform.onesa.eu') ||
  (local && ctx.environment === 'development' && process.argv.includes('--local-fixture')), 'OWNED_PROBE_ORIGIN');
need(/^[a-f0-9]{40}$/.test(ctx.binding.candidate_commit) && /^[a-f0-9-]{36}$/.test(ctx.operation_id) && ctx.users.length === 2 &&
  ctx.users.every(u => /^[a-f0-9-]{36}$/.test(u.id) && /^release-audit-[0-9]+-[a-f0-9]{24}@example\.com$/.test(u.email)), 'OWNED_FIXTURE_SCOPE');
const phase = process.argv.includes('--verify') ? 'verify' : 'prepare';
const apiOnly = process.argv.includes('--api-only');
const output = ctx.output_dir, base = '/api/v1/cybersecurity';
const report = {binding:ctx.binding, operation_id:ctx.operation_id, environment:ctx.environment,
  workflow_run_id:0, status:'FAIL', checks:{}, source_commit:ctx.binding.candidate_commit,
  scope:apiOnly ? 'Owned synthetic API evidence; frontend acceptance separate' : 'Owned synthetic API and rendered native UI'};
function save(name, data) {
  fs.writeFileSync(path.join(output, name), JSON.stringify(data), {mode:0o600, flag:'wx'});
}
async function main() {
  const browser = await chromium.launch({headless:true});
  let context;
  try {
    report.browser_version = browser.version();
    context = await browser.newContext({baseURL:origin,
      extraHTTPHeaders:ctx.bypass ? {'x-vercel-protection-bypass':ctx.bypass} : {},
      ...(phase === 'verify' ? {storageState:path.join(output, 'cybersecurity-browser-state.json')} : {})});
    const page = await context.newPage(), errors = [];
    page.on('pageerror', e => errors.push(e.name));
    await context.route('**/*', route => {
      const u = new URL(route.request().url());
      return !['http:', 'https:'].includes(u.protocol) || u.origin === origin ? route.continue() : route.abort();
    });
    async function headers() { return {Origin:origin, 'X-CSRF-Token':(await context.cookies(origin)).find(c => c.name === 'onesa_csrf')?.value || ''}; }
    async function api(method, target, data, status=200) {
      need(target.startsWith('/api/v1/') && !target.includes('..'), 'PROBE_API_PATH');
      const response = await page.request.fetch(target, {method, headers:await headers(), ...(data === undefined ? {} : {data})});
      need(response.status() === status, 'PROBE_STATUS_' + method + '_' + response.status());
      return status === 204 ? null : response.json();
    }
    if (phase === 'prepare') {
      await api('POST', '/api/v1/auth/login', {email:ctx.users[0].email, password:ctx.users[0].password});
    } else {
      need((await api('GET', '/api/v1/auth/me')).id === ctx.users[0].id, 'PERSISTED_SESSION_OWNER');
      report.checks.session_persistence = 'PASS';
    }
    if (!local) need((await context.cookies(origin)).find(c => c.name === 'onesa_session')?.secure, 'SECURE_SESSION_COOKIE');
    report.checks.authentication = 'PASS';
    const readiness = await api('GET', base + '/readiness');
    need(readiness.enabled && readiness.schema === 'ot-security-evidence/v1' && readiness.provider_required === false, 'SCOPED_READINESS');
    report.checks.cybersecurity_scoped_readiness = 'PASS';
    let owned;
    if (phase === 'prepare') {
      const asset = await api('POST', base + '/assets', {name:'Owned synthetic qualification gateway', identity:'qual-' + ctx.operation_id,
        zone:'Isolated release verification', criticality:'high', review_note:'Reviewed synthetic owner inventory; no real OT processing'}, 201);
      const source = await api('POST', base + '/sources', {name:'Owned synthetic release source', namespace:'release-qualification', modes:['simulated'],
        expected_interval_seconds:3600, review_note:'Explicit synthetic release scope; no external source'}, 201);
      await api('POST', base + `/sources/${source.id}/mappings`, {asset_id:asset.id, namespace:'qualification', external_asset:'gateway',
        review_note:'Reviewed synthetic association to owned local asset'}, 201);
      const events = Array.from({length:5}, (_, index) => ({schemaVersion:'ot-security-evidence/v1', producerNamespace:'release-qualification',
        sourceEventId:ctx.operation_id + '-' + index, occurredAt:new Date().toISOString(), mode:'simulated', scenarioRunId:ctx.operation_id,
        eventType:'auth.authentication_failed', assetRef:{namespace:'qualification', assetId:'gateway', componentId:null},
        summary:'Explicit synthetic rejected access observation; no incident claimed', quality:'good', producerVersion:'owner-qualification/1',
        attributes:{service:'synthetic-release', outcome:'denied', reasonCode:'SYNTHETIC_REJECTION'}}));
      const response = await page.request.post(base + '/ingest', {headers:{Authorization:'Bearer ' + source.ingestion_token}, data:{events}});
      need(response.status() === 200, 'SCOPED_BEARER_INGESTION');
      const repeat = await page.request.post(base + '/ingest', {headers:{Authorization:'Bearer ' + source.ingestion_token}, data:{events}});
      need(repeat.status() === 200 && (await repeat.json()).duplicates === 5, 'IDEMPOTENT_DELIVERY');
      const workspace = await api('GET', base + '/workspace?mode=simulated');
      const finding = workspace.findings.find(f => f.asset_id === asset.id);
      need(finding && finding.mode === 'simulated', 'DETERMINISTIC_MAPPED_FINDING');
      const investigation = await api('POST', base + '/investigations', {finding_id:finding.id, title:'Owned synthetic qualification investigation'}, 201);
      const decision = await api('POST', base + `/investigations/${investigation.id}/decisions`, {
        revision:investigation.revision, action:'acknowledge', note:'Owner acknowledges synthetic qualification evidence only', evidence_ids:[]});
      const summary = await api('POST', base + '/summaries', {investigation_id:investigation.id, expected_sha256:investigation.sha256}, 201);
      need(summary.result.status === 'deterministic', 'NO_PROVIDER_CHECKLIST');
      await api('POST', base + `/sources/${source.id}/policies`, {auth_threshold:4, review_note:'Actual committed synthetic policy change for native evidence verification'}, 201);
      const live = await api('GET', base + '/workspace?mode=live');
      need(live.events.some(e => e.wire.producerNamespace === 'onesa-owned-configuration' && e.event_type === 'config.changed'), 'ACTUAL_COMMITTED_NATIVE_EVIDENCE');
      await api('POST', base + `/sources/${source.id}/revoke`);
      need((await page.request.post(base + '/ingest', {headers:{Authorization:'Bearer ' + source.ingestion_token}, data:{events}})).status() === 401, 'REVOKED_SOURCE_REJECTED');
      owned = {asset:asset.id, source:source.id, finding:finding.id, investigation:investigation.id, snapshot_sha256:investigation.sha256,
        revision:decision.revision, summary:summary.id};
      save('cybersecurity-prepared.json', owned);
      for (const key of ['cybersecurity_ingestion', 'cybersecurity_findings', 'cybersecurity_native_configuration', 'cybersecurity_revocation']) report.checks[key] = 'PASS';
    } else owned = privateJSON(path.join(output, 'cybersecurity-prepared.json'));
    const detail = await api('GET', base + `/investigations/${owned.investigation}`);
    need(detail.investigation.sha256 === owned.snapshot_sha256 && detail.investigation.status === 'acknowledged' &&
      detail.summaries.some(s => s.id === owned.summary), 'IMMUTABLE_INVESTIGATION_PERSISTENCE');
    await api('GET', base + `/assets/${owned.asset}`);
    await api('GET', base + `/findings/${owned.finding}`);
    const exported = await api('GET', base + `/export?mode=simulated&source_id=${owned.source}`);
    need(exported.events.length === 5 && exported.events.every(e => e.mode === 'simulated' && e.producerNamespace === 'release-qualification'), 'OWNED_WIRE_EXPORT');
    report.checks.cybersecurity_export = 'PASS';
    report.checks.cybersecurity_decisions = 'PASS';
    report.checks.database_persistence = 'PASS';
    const other = await browser.newContext({baseURL:origin, extraHTTPHeaders:ctx.bypass ? {'x-vercel-protection-bypass':ctx.bypass} : {}});
    try {
      need((await other.request.post('/api/v1/auth/login', {headers:{Origin:origin}, data:{email:ctx.users[1].email, password:ctx.users[1].password}})).status() === 200, 'SECOND_OWNER_LOGIN');
      for (const target of [`/assets/${owned.asset}`, `/findings/${owned.finding}`, `/investigations/${owned.investigation}`])
        need((await other.request.get(base + target)).status() === 404, 'FOREIGN_OWNER_DENIED');
      const foreign = await other.request.get(base + '/workspace?mode=simulated');
      need(foreign.status() === 200 && !(await foreign.json()).findings.length, 'AGGREGATE_ISOLATION');
    } finally { await other.close(); }
    report.checks.owner_isolation = 'PASS';
    if (!apiOnly) {
      await page.goto(`/industrial/cybersecurity?mode=simulated&view=Investigations&finding=${owned.finding}`);
      await expect(page.getByRole('heading', {name:'Cybersecurity', exact:true})).toBeVisible();
      await expect(page.getByText('Owned synthetic qualification investigation', {exact:true}).first()).toBeVisible();
      await page.reload();
      await expect(page.getByText('Owned synthetic qualification investigation', {exact:true}).first()).toBeVisible();
      need(!await page.locator('canvas').count() && !errors.length, 'INDEPENDENT_RENDERED_WORKSPACE');
      await page.screenshot({path:path.join(output, 'cybersecurity-' + phase + '.png'), fullPage:true});
      report.checks.cybersecurity_ui = 'PASS';
    }
    if (phase === 'prepare') {
      await context.storageState({path:path.join(output, 'cybersecurity-browser-state.json')});
      fs.chmodSync(path.join(output, 'cybersecurity-browser-state.json'), 0o600);
    }
    report.checks.optional_sources_absent = 'PASS';
    report.checks.tls = local ? 'LOCAL_FIXTURE_ONLY' : 'PASS';
    report.status = 'PASS';
  } catch (error) {
    report.failure_category = /^[A-Z0-9_]+$/.test(error.message || '') ? error.message : error.constructor.name;
    throw error;
  } finally {
    await context?.close(); await browser.close();
    save('cybersecurity-' + phase + '-ui.json', report);
  }
}
main().catch(() => { console.error('Oracle cybersecurity observation failed; inspect private receipt.'); process.exitCode = 1; });
