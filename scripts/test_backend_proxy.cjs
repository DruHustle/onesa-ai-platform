/* Execute the real proxy with an isolated fetch transport and synthetic credentials. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const {createRequire} = require('node:module');
const chat = path.resolve(__dirname, '../onesa-ai-platform-frontend/apps/chat');
const ts = createRequire(path.join(chat, 'package.json'))('typescript');
const source = fs.readFileSync(path.join(chat, 'src/lib/backend.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
const exported = {};
let upstream;
let fetches = 0;
let trustLoaded = false;
const context = {
  exports: exported, Request, Response, Headers, URL, AbortSignal, crypto: webcrypto,
  process: {env: {ONESA_API_URL: 'https://staging-api.example.invalid'}},
  require: name => {
    if (name === 'server-only') return {};
    assert.equal(name, './server/tls-trust');
    const policySource = fs.readFileSync(path.join(chat, 'src/lib/server/tls-trust.ts'), 'utf8');
    const policyCode = ts.transpileModule(policySource, {compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
    }}).outputText;
    const policyExports = {};
    vm.runInNewContext(policyCode, {exports: policyExports, process: {env: {}},
      require: dependency => {assert(['node:tls', 'node:crypto'].includes(dependency)); return require(dependency);},
    });
    assert.equal(policyExports.tlsTrustPolicy.blockedCAAbsent, true);
    trustLoaded = true;
    return policyExports;
  },
  fetch: async (url, options) => {
    assert.equal(trustLoaded, true, 'TLS initialization must finish before gateway transport');
    fetches++; upstream = {url, ...options}; return Response.json({ok:true});
  },
};
vm.runInNewContext(compiled, context, {filename: 'backend-proxy-regression.js'});

async function main() {
  const response = await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me', {
    headers: {
      'x-vercel-protection-bypass': 'synthetic-provider-credential',
      'x-vercel-set-bypass-cookie': 'true',
      'x-vercel-oidc-token': 'synthetic-provider-identity',
      cookie: '_vercel_sso_token=synthetic-provider-cookie; onesa_session=synthetic-session; onesa_csrf=synthetic-csrf; locale=en',
      'x-csrf-token': 'synthetic-csrf',
      origin: 'https://preview.example.invalid',
    },
  }));
  assert.equal(response.status, 200);
  assert.equal(upstream.url.origin, 'https://staging-api.example.invalid');
  assert.equal(upstream.headers.get('x-vercel-protection-bypass'), null);
  assert.equal(upstream.headers.get('x-vercel-set-bypass-cookie'), null);
  assert.equal(upstream.headers.get('x-vercel-oidc-token'), null);
  assert.equal(upstream.headers.get('cookie'), 'onesa_session=synthetic-session; onesa_csrf=synthetic-csrf');
  assert.equal(upstream.headers.get('x-csrf-token'), 'synthetic-csrf');
  assert.equal(upstream.headers.get('origin'), 'https://preview.example.invalid');
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  const requestIds = new Set();
  for (const headers of [
    {},
    {cookie: '_vercel_sso_token=synthetic-provider-cookie'},
    {cookie: 'onesa_csrf=synthetic-csrf'},
    {cookie: 'onesa_session='},
    {cookie: 'onesa_session= ; onesa_session='},
    {authorization: 'Bearer synthetic-non-session', 'x-request-id': 'untrusted-correlation'},
  ]) {
    const count = fetches;
    const result = await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me', {headers}));
    assert.equal(result.status, 401);
    assert.equal(fetches, count, 'A proven absent session must not wake the backend');
    assert.equal(result.headers.get('cache-control'), 'no-store');
    assert.equal(result.headers.get('x-content-type-options'), 'nosniff');
    assert.equal(result.headers.get('set-cookie'), null);
    const body = await result.json();
    assert.deepEqual(Object.keys(body.error).sort(), ['code', 'message', 'request_id']);
    assert.equal(body.error.code, 'unauthorized');
    assert.equal(body.error.message, 'Sign in to continue');
    assert.match(body.error.request_id, uuid);
    assert.equal(result.headers.get('x-request-id'), body.error.request_id);
    assert.equal(requestIds.has(body.error.request_id), false);
    requestIds.add(body.error.request_id);
  }
  for (const cookie of [
    'onesa_session=synthetic-session',
    'onesa_session=expired-or-revoked',
    'onesa_session=""',
    'onesa_session="synthetic-session"',
    'onesa_session=; onesa_session=synthetic-session',
    'onesa_session=synthetic-session; onesa_session=',
  ]) {
    const count = fetches;
    assert.equal((await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me', {headers:{cookie}}))).status, 200);
    assert.equal(fetches, count + 1, 'Every possibly nonempty session delegates to real backend authorization');
    assert.equal(upstream.headers.get('cookie'), cookie);
  }
  for (const [method, route] of [
    ['POST', '/api/v1/auth/login'], ['POST', '/api/v1/auth/register'],
    ['POST', '/api/v1/auth/me'], ['HEAD', '/api/v1/auth/me'], ['OPTIONS', '/api/v1/auth/me'],
    ['GET', '/api/v1/auth/me/'], ['GET', '/api/v1/models'], ['GET', '/api/v1/knowledge/documents'],
    ['GET', '/health'], ['GET', '/ready'],
  ]) {
    const count = fetches;
    await exported.proxy(new Request('https://preview.example.invalid' + route, {method}));
    assert.equal(fetches, count + 1, 'The fast path is confined to one exact GET');
  }
  for (const [variable, value] of [['ONESA_API_URL', 'https://invalid.example/private'], ['ONESA_PROXY_TIMEOUT_SECONDS', '0']]) {
    const prior = context.process.env[variable], count = fetches;
    context.process.env[variable] = value;
    assert.equal((await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me'))).status, 503);
    assert.equal(fetches, count, 'Operator configuration fails closed before the fast path');
    if (prior === undefined) delete context.process.env[variable]; else context.process.env[variable] = prior;
  }
  // A sleeping upstream never responds: absent-session startup still completes immediately.
  context.fetch = () => {fetches++; return new Promise(() => {});};
  const count = fetches, started = performance.now();
  let timer;
  try {
    const result = await Promise.race([
      exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me')),
      new Promise((_, reject) => {timer=setTimeout(() => reject(new Error('Anonymous startup waited for sleeping backend')), 250);}),
    ]);
    assert.equal(result.status, 401);
    assert.equal(fetches, count);
    assert.ok(performance.now() - started < 250);
  } finally {clearTimeout(timer);}
  // A cookie-bearing request remains dependent on the actual upstream outcome.
  context.fetch = async () => {fetches++; return Response.json({error:{code:'unauthorized'}}, {status:401});};
  assert.equal((await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me', {headers:{cookie:'onesa_session=revoked'}}))).status, 401);
  assert.equal(fetches, count + 1);
  context.fetch = async () => {fetches++; throw new Error('Synthetic sleeping backend unavailable');};
  assert.equal((await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me', {headers:{cookie:'onesa_session=unverified'}}))).status, 503);
  assert.equal(fetches, count + 2);
  console.log('Proxy credential/session boundary: PASS; 6 absent-session, 6 delegated-cookie, 10 unchanged-route, configuration, sleeping-upstream and failed-session cases');
}
main().catch(error => {console.error(error);process.exitCode=1;});
