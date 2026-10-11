/* Execute the real proxy with an isolated fetch transport and synthetic credentials. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createRequire} = require('node:module');
const chat = path.resolve(__dirname, '../onesa-ai-platform-frontend/apps/chat');
const ts = createRequire(path.join(chat, 'package.json'))('typescript');
const source = fs.readFileSync(path.join(chat, 'src/lib/backend.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
const exported = {};
let upstream;
const context = {
  exports: exported, Request, Response, Headers, URL, AbortSignal,
  process: {env: {ONESA_API_URL: 'https://staging-api.example.invalid'}},
  require: name => {assert.equal(name, 'server-only'); return {};},
  fetch: async (url, options) => {upstream = {url, ...options}; return Response.json({ok:true});},
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
  await exported.proxy(new Request('https://preview.example.invalid/api/v1/auth/me', {
    headers: {cookie: '_vercel_sso_token=synthetic-provider-cookie'},
  }));
  assert.equal(upstream.headers.get('cookie'), null);
  console.log('Proxy credential boundary: PASS; application session/CSRF preserved');
}
main().catch(error => {console.error(error);process.exitCode=1;});
