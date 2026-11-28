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

async function identityMethodBootstrap() {
  const compile = relative => ts.transpileModule(fs.readFileSync(path.join(chat, relative), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
  }).outputText;
  const methods = {}, bootstrap = {};
  vm.runInNewContext(compile('src/lib/identity-method.ts'), {exports: methods, URL});
  vm.runInNewContext(compile('src/lib/server/identity-method.ts'), {
    exports: bootstrap, Request, AbortSignal,
    require: name => {
      if (name === 'server-only') return {};
      if (name === '../backend') return exported;
      assert.equal(name, '../identity-method');
      return methods;
    },
  });
  for (const [status, body, expected] of [
    [200, {enabled:false, account_url:null}, {enabled:false, account_url:null}],
    [200, {enabled:true, account_url:'https://account.example.test/account'}, {enabled:true, account_url:'https://account.example.test/account'}],
    [404, {detail:'Not Found'}, {enabled:false, account_url:null}],
    ...[401, 403, 503].map(status => [status, {error:{message:'synthetic'}}, {enabled:false, account_url:null, unavailable:true}]),
    ...[{}, {enabled:'false', account_url:null}, {enabled:true, account_url:null},
      {enabled:true, account_url:'javascript:synthetic'},
      {enabled:true, account_url:'https://synthetic:password@account.example.test/account'},
    ].map(body => [200, body, {enabled:false, account_url:null, unavailable:true}]),
  ]) {
    context.fetch = async (url, options) => {
      assert.equal(url.pathname, '/api/v1/auth/onesa/config');
      assert.equal(options.headers.get('cookie'), null);
      assert.equal(options.headers.get('authorization'), null);
      assert.equal(options.cache, 'no-store');
      assert.equal(options.redirect, 'manual');
      return Response.json(body, {status});
    };
    assert.deepEqual(JSON.parse(JSON.stringify(await bootstrap.loadIdentityMethod(true))), expected);
    const hosted = await bootstrap.loadIdentityMethod(false);
    assert.equal(Boolean(hosted.unavailable), !expected.enabled);
  }
  context.fetch = async () => new Response('invalid synthetic JSON', {status:200});
  assert.equal((await bootstrap.loadIdentityMethod()).unavailable, true);
  context.fetch = (_url, options) => new Promise((_, reject) => {
    options.signal.addEventListener('abort', () => reject(options.signal.reason), {once:true});
  });
  let watchdog;
  try {
    const result = await Promise.race([
      bootstrap.loadIdentityMethod(),
      new Promise((_, reject) => {watchdog=setTimeout(() => reject(new Error('Sign-in bootstrap deadline exceeded')), 3000);}),
    ]);
    assert.equal(result.unavailable, true);
  } finally {clearTimeout(watchdog);}
  console.log('Identity method bootstrap: PASS; native/shared rendering capability, explicit legacy404, credential-free transport, malformed/unavailable responses and bounded timeout');
}

async function nativeTransport() {
  const token = 'nai_' + 's'.repeat(43);
  const credential = {origin: 'onesaai://native', authorization: 'Bearer ' + token};
  const id = '19f22161-4fc9-4e75-a11e-2587a03a1011';
  context.fetch = async (url, options) => {
    fetches++; upstream = {url, ...options};
    return Response.json({ok: true}, {headers: {'set-cookie': 'onesa_session=must-not-reach-native; HttpOnly'}});
  };
  for (const [methods, route] of [
    ['GET', '/auth/me'], ['GET', '/models'], ['GET', '/models/default'],
    ['GET|POST', '/conversations'], ['GET|PATCH|DELETE', '/conversations/' + id],
    ['POST', '/conversations/' + id + '/cancel'], ['POST', '/chat/completions'],
    ['GET|POST', '/knowledge/documents'], ['GET|DELETE', '/knowledge/documents/' + id],
    ['POST', '/knowledge/documents/' + id + '/reindex'], ['POST', '/knowledge/search'],
    ['GET', '/agents/tools'], ['GET|POST', '/agents/runs'],
    ['GET', '/agents/runs/' + id], ['POST', '/agents/runs/' + id + '/cancel'],
    ['GET|POST', '/travel/trips'], ['GET|PUT|DELETE', '/travel/trips/' + id],
    ['POST', '/auth/native/logout'],
  ]) for (const method of methods.split('|')) {
    const count = fetches;
    const response = await exported.proxy(new Request('https://platform.example.test/api/v1' + route, {method, headers: credential}));
    assert.equal(response.status, 200, method + ' ' + route);
    assert.equal(fetches, count + 1);
    assert.equal(upstream.headers.get('origin'), 'onesaai://native');
    assert.equal(upstream.headers.get('authorization'), 'Bearer ' + token);
    assert.equal(upstream.headers.get('cookie'), null);
    assert.equal(upstream.headers.get('x-csrf-token'), null);
    assert.equal(upstream.redirect, 'manual');
    assert.equal(response.headers.get('set-cookie'), null, 'Native API cannot install browser authority');
  }
  for (const route of ['start', 'token']) {
    assert.equal((await exported.proxy(new Request('https://platform.example.test/api/v1/auth/native/' + route,
      {method: 'POST', headers: {origin: 'onesaai://native'}}))).status, 200);
    assert.equal(upstream.headers.get('authorization'), null);
  }
  for (const change of [
    {origin: 'https://platform.example.test'}, {origin: 'https://external.example.test'},
    {origin: 'null'}, {origin: ''}, {cookie: ''}, {cookie: 'onesa_session=synthetic'},
    {'x-csrf-token': ''}, {'sec-fetch-site': 'same-origin'}, {'sec-fetch-site': 'cross-site'},
  ]) {
    const count = fetches;
    const response = await exported.proxy(new Request('https://platform.example.test/api/v1/auth/me',
      {headers: {...credential, ...change}}));
    assert.equal(response.status, 403);
    assert.equal(fetches, count, 'Mixed/native browser credentials are rejected before transport');
  }
  for (const [method, route] of [
    ['GET', '/auth/sessions'], ['POST', '/auth/refresh'], ['POST', '/auth/logout'],
    ['GET', '/auth/native/requests/' + id], ['POST', '/auth/native/requests/' + id + '/approve'],
    ['POST', '/inference/completions'], ['GET', '/documentation/access'],
    ['GET', '/industrial/investigations'], ['GET', '/twins/assets'],
    ['GET', '/cybersecurity/findings'], ['OPTIONS', '/models'],
    ['POST', '/travel/trips/' + id], ['GET', '/conversations/' + id + '/extra'],
  ]) {
    const count = fetches;
    assert.equal((await exported.proxy(new Request('https://platform.example.test/api/v1' + route,
      {method, headers: credential}))).status, 403);
    assert.equal(fetches, count, 'Native transport has no generic authenticated API access');
  }
  context.fetch = async () => new Response(null, {status: 307, headers: {location: '/api/v1/auth/me'}});
  assert.equal((await exported.proxy(new Request('https://platform.example.test/api/v1/models',
    {headers: credential}))).status, 503);
  context.fetch = async () => Response.json({error: {code: 'unauthorized'}}, {status: 401});
  assert.equal((await exported.proxy(new Request('https://platform.example.test/api/v1/auth/me',
    {headers: credential}))).status, 401, 'The proxy never confers identity on a native origin');
  console.log('Native proxy boundary: PASS; exact product routes, issuer-authorized me, native cookie isolation, mixed/browser rejection and redirects refused');
}

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

  context.fetch = async (url, options) => {
    fetches++;
    upstream = {url, ...options};
    return new Response('synthetic cookie response', {status:200, headers:[
    ['set-cookie', 'onesa_session=synthetic-session; Path=/; HttpOnly; Secure; SameSite=Lax'],
    ['set-cookie', 'onesa_csrf=synthetic-csrf; Path=/; Secure; SameSite=Lax'],
    ['set-cookie', 'onesa_identity_flow=synthetic-flow; Path=/; HttpOnly; Secure; SameSite=Lax'],
    ['set-cookie', '_vercel_sso_token=provider-cookie; Path=/; Secure'],
    ['set-cookie', 'unexpected=untrusted; Path=/'],
    ]});
  };
  const cookieResponse = await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/onesa/exchange'));
  assert.deepEqual(cookieResponse.headers.getSetCookie().map(value => value.split(';', 1)[0]), [
    'onesa_session=synthetic-session',
    'onesa_csrf=synthetic-csrf',
    'onesa_identity_flow=synthetic-flow',
  ], 'Only application-owned cookies may cross the BFF boundary');
  assert.equal(cookieResponse.headers.get('cache-control'), 'no-store');

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
    ['POST', '/api/v1/auth/me'], ['HEAD', '/api/v1/auth/me'], ['OPTIONS', '/api/v1/auth/me'],
    ['GET', '/api/v1/auth/me/'], ['GET', '/api/v1/models'], ['GET', '/api/v1/knowledge/documents'],
    ['GET', '/health'], ['GET', '/ready'],
  ]) {
    const count = fetches;
    await exported.proxy(new Request('https://preview.example.invalid' + route, {method}));
    assert.equal(fetches, count + 1, 'The fast path is confined to one exact GET');
  }
  for (const route of ['login', 'register', 'recovery/request', 'recovery/complete']) {
    const before = fetches;
    const result = await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/' + route, {method:'POST'}));
    assert.equal(result.status, 403);
    assert.equal((await result.json()).error.code, 'shared_sign_in_required');
    assert.equal(fetches, before);
  }
  const configuredBase = context.process.env.ONESA_API_URL;
  context.process.env.ONESA_API_URL = 'http://api:8000';
  for (const [origin, hosted, expected] of [
    ['http://localhost:3100', false, 200],
    ['http://localhost:3100', true, 403],
    ['https://preview.example.invalid', false, 403],
  ]) {
    if (hosted) context.process.env.VERCEL = '1';
    else delete context.process.env.VERCEL;
    const result = await exported.proxy(new Request(origin + '/api/v1/auth/register', {method:'POST'}));
    assert.equal(result.status, expected);
  }
  context.process.env.ONESA_PUBLIC_ORIGIN = 'http://localhost:3100';
  const listener = 'http://0.0.0.0:3000/api/v1/auth/register';
  for (const [host, expected] of [['localhost:3100', 200], ['public.example.invalid', 403], ['localhost:9999', 403]]) {
    const result = await exported.proxy(new Request(listener, {method:'POST', headers:{host}}));
    assert.equal(result.status, expected);
  }
  context.process.env.ONESA_PUBLIC_ORIGIN = 'https://platform.example.invalid';
  const hostedOrigin = await exported.proxy(new Request('http://localhost/api/v1/auth/register', {method:'POST', headers:{host:'localhost'}}));
  assert.equal(hostedOrigin.status, 403);
  delete context.process.env.ONESA_PUBLIC_ORIGIN;
  context.process.env.ONESA_API_URL = configuredBase;
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
  const unavailable = await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me', {headers:{cookie:'onesa_session=unverified'}}));
  assert.equal(unavailable.status, 503);
  assert.equal(unavailable.headers.get('cache-control'), 'no-store');
  assert.equal(unavailable.headers.get('x-content-type-options'), 'nosniff');
  assert.equal(fetches, count + 2);
  console.log('Proxy credential/session boundary: PASS; 6 absent-session, 6 delegated-cookie, 8 unchanged-route, 4 hosted credential denials, configuration, sleeping-upstream and failed-session cases');
  await legacyMobileCallbackBoundary();
  await nativeTransport();
  await identityMethodBootstrap();
}

async function legacyMobileCallbackBoundary() {
  const state = 'native_' + 'a'.repeat(43);
  const callback = 'onesaai://account/callback?state=' + state;
  const path = '/api/v1/auth/onesa/callback';
  let destination = callback;
  let status = 303;
  context.fetch = async () => {
    fetches++;
    return new Response(null, {status, headers: {location: destination}});
  };
  const request = (route = path, method = 'GET', headers = {}) =>
    new Request('https://preview.example.invalid' + route, {method, headers});
  const valid = await exported.proxy(request());
  assert.equal(valid.status, 303);
  assert.equal(valid.headers.get('location'), callback, 'Existing browser-mediated mobile callback remains exact');
  assert.equal(valid.headers.get('cache-control'), 'no-store');
  for (const invalid of [
    'onesaai://other/callback?state=' + state,
    'onesaai://account/other?state=' + state,
    'onesaai://user@account/callback?state=' + state,
    callback + '#unexpected',
    callback + '&state=' + state,
    'onesaai://account/callback?state=invalid',
  ]) {
    destination = invalid;
    assert.equal((await exported.proxy(request())).status, 503);
  }
  destination = callback;
  assert.equal((await exported.proxy(request('/api/v1/models'))).status, 503);
  assert.equal((await exported.proxy(request(path, 'POST'))).status, 503);
  status = 302;
  assert.equal((await exported.proxy(request())).status, 503);
  status = 303;
  const priorFetches = fetches;
  assert.equal((await exported.proxy(request(path, 'GET', {origin: 'onesaai://native'}))).status, 403);
  assert.equal(fetches, priorFetches, 'New native transport cannot enter the browser callback path');
  console.log('Legacy mobile callback boundary: PASS; exact browser callback preserved, invalid redirects and new native transport rejected');
}
main().catch(error => {console.error(error);process.exitCode=1;});
