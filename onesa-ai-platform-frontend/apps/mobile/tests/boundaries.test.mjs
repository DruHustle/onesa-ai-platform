import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { z } from 'zod';
import { Client } from '../src/client.ts';
import { apiURL, authorization, callbackCode, CALLBACK, KNOWLEDGE_DOCUMENTS, KNOWLEDGE_SEARCH, NATIVE_ORIGIN, ORIGIN, validCredential } from '../src/protocol.ts';
import { chatEvents } from '../../../packages/api-client/sse.ts';

const id = '765fd0f2-9f1b-48a6-bf1e-b5887b871458';
const state = 's'.repeat(64), code = 'c'.repeat(64);
const credential = { access_token: 'synthetic_native_' + 'a'.repeat(64), expires_at: '2099-01-01T00:00:00Z', user: { id, email: 'native@example.invalid', display_name: 'Synthetic native user' } };
const encoder = new TextEncoder();

test('authorization is bound to the canonical browser origin, path and request', () => {
  assert.equal(authorization({ request_id: id, authorize_url: `${ORIGIN}/auth/native?request=${id}` }).request_id, id);
  for (const url of [`https://example.invalid/auth/native?request=${id}`, `${ORIGIN}/auth/native?request=${id}&request=${id}`, `${ORIGIN}/auth/native?request=${id}&next=https://example.invalid`, `${ORIGIN}/auth/native?request=${id}#x`, `${ORIGIN}/auth/native/other?request=${id}`, `https://user@platform.onesa.eu/auth/native?request=${id}`]) assert.throws(() => authorization({ request_id: id, authorize_url: url }));
});

test('native callback accepts only one code and the pending state at the exact callback', () => {
  assert.equal(callbackCode(`${CALLBACK}?state=${state}&code=${code}`, state), code);
  for (const url of [`${CALLBACK}?state=wrong&code=${code}`, `${CALLBACK}?state=${state}&code=${code}&code=${code}`, `${CALLBACK}?state=${state}&code=${code}&access_token=bad`, `https://auth/callback?state=${state}&code=${code}`, `onesaai://auth/wrong?state=${state}&code=${code}`, `${CALLBACK}?state=${state}&code=${code}#fragment`, `onesaai://user@auth/callback?state=${state}&code=${code}`]) assert.throws(() => callbackCode(url, state));
});

test('routes cannot send credentials to arbitrary, admin or machine-control destinations', () => {
  assert.equal(apiURL(`/conversations/${id}/cancel`), `${ORIGIN}/api/v1/conversations/${id}/cancel`);
  assert.equal(apiURL(`${KNOWLEDGE_DOCUMENTS}?limit=100&offset=100`), `${ORIGIN}/api/v1/knowledge/documents?limit=100&offset=100`);
  for (const path of ['https://example.invalid', '//example.invalid', '/models#x', '/models?next=x', '/models?limit=200', '/auth/password', '/admin/users', '/industrial/control', '/conversations/../../admin', '/conversations/%2e%2e', '/auth/native/token?next=x', '/documents', '/search']) assert.throws(() => apiURL(path));
});

test('native Knowledge operations exist in the generated backend contract', async () => {
  const contract = JSON.parse(await readFile(new URL('../../../../docs/api/openapi.json', import.meta.url), 'utf8'));
  assert.ok(contract.paths[`/api/v1${KNOWLEDGE_DOCUMENTS}`]?.get, 'Document listing must match the backend GET route');
  assert.ok(contract.paths[`/api/v1${KNOWLEDGE_SEARCH}`]?.post, 'Knowledge search must match the backend POST route');
  const destinations = [];
  const client = new Client(async (url, init) => { destinations.push([new URL(url).pathname, init.method]); return Response.json({}); }, () => { throw new Error('Valid Knowledge requests must not expire sign-in'); });
  client.setCredential(credential);
  await client.json(z.unknown(), `${KNOWLEDGE_DOCUMENTS}?limit=100`);
  await client.json(z.unknown(), KNOWLEDGE_SEARCH, 'POST', { query: 'Synthetic query', document_ids: [] });
  assert.deepEqual(destinations, [[`/api/v1${KNOWLEDGE_DOCUMENTS}`, 'GET'], [`/api/v1${KNOWLEDGE_SEARCH}`, 'POST']]);
});

test('expired and malformed persisted credentials never become a session', () => {
  assert.equal(validCredential(credential).user.id, id);
  assert.throws(() => validCredential({ ...credential, expires_at: '2000-01-01T00:00:00Z' }));
  assert.throws(() => validCredential({ ...credential, access_token: 'value\r\nCookie: bad' }));
  assert.throws(() => validCredential({ ...credential, user: { ...credential.user, id: 'not-a-uuid' } }));
});

test('native API emits bearer and fixed Origin, no cookies or redirect-following', async () => {
  let outgoing;
  const client = new Client(async (url, init) => { outgoing = { url, init }; return Response.json({ ok: true }); }, () => {});
  client.setCredential(credential);
  assert.deepEqual(await client.json(z.object({ ok: z.boolean() }), '/models'), { ok: true });
  assert.equal(outgoing.init.headers.Origin, NATIVE_ORIGIN);
  assert.equal(outgoing.init.headers.Authorization, `Bearer ${credential.access_token}`);
  assert.equal(outgoing.init.credentials, 'omit');
  assert.equal(outgoing.init.redirect, 'error');
  assert.equal(outgoing.init.headers.Cookie, undefined);
  assert.equal(outgoing.init.headers['X-CSRF-Token'], undefined);
});

test('public PKCE start never receives a retained access token', async () => {
  let headers;
  const client = new Client(async (_url, init) => { headers = init.headers; return Response.json({ ok: true }); }, () => {});
  client.setCredential(credential);
  await client.json(z.unknown(), '/auth/native/start', 'POST', { code_challenge: 'public-challenge', state });
  assert.equal(headers.Authorization, undefined);
});

test('uncertain writes are issued once and not automatically retried', async () => {
  let calls = 0;
  const client = new Client(async () => { calls++; throw new TypeError('synthetic connection lost'); }, () => {});
  client.setCredential(credential);
  await assert.rejects(client.request('/agents/runs', 'POST', { goal: 'Synthetic goal' }));
  assert.equal(calls, 1);
});

test('authentication failure locks the session without rendering a private error body', async () => {
  let expired = 0;
  const client = new Client(async () => new Response('synthetic private debug trace', { status: 401 }), () => { expired++; });
  client.setCredential(credential);
  await assert.rejects(client.request('/models'), error => error.status === 401 && !error.message.includes('private debug'));
  assert.equal(expired, 1);
});

test('an account switch discards a delayed previous account response', async () => {
  let release;
  const client = new Client(() => new Promise(resolve => { release = resolve; }), () => {});
  client.setCredential(credential);
  const pending = client.json(z.unknown(), '/conversations');
  client.setCredential({ ...credential, access_token: 'synthetic_other_' + 'b'.repeat(64) });
  release(Response.json({ private: 'old account data' }));
  await assert.rejects(pending, /Account changed/);
});

test('sign-out also cancels a response whose headers have already arrived', async () => {
  let source;
  const body = new ReadableStream({ start(controller) { source = controller; } });
  const client = new Client(async () => new Response(body), () => {});
  client.setCredential(credential);
  const response = await client.request('/conversations');
  const pending = response.text();
  client.setCredential(null);
  await assert.rejects(pending, /cancelled/);
  assert.throws(() => source.enqueue(encoder.encode('old private body')));
});

test('oversized responses are refused before UI parsing', async () => {
  const client = new Client(async () => new Response('x'.repeat(2 * 1024 * 1024 + 1)), () => {});
  client.setCredential(credential);
  await assert.rejects(client.json(z.unknown(), KNOWLEDGE_DOCUMENTS), /exceeded/);
});

test('stream completion requires persisted-terminal metadata and preserves UTF-8 chunks', async () => {
  const data = `event: message_start\ndata: ${JSON.stringify({ conversation_id: id, run_id: id })}\n\nevent: content_delta\ndata: {"text":"Hello 🌱"}\n\nevent: message_end\ndata: ${JSON.stringify({ message_id: id, model: { backend: 'mock', model_identifier: 'synthetic', real_inference: false } })}\n\n`;
  const bytes = encoder.encode(data), body = new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(Uint8Array.of(byte)); controller.close(); } });
  const events = [];
  for await (const event of chatEvents(body)) events.push(event);
  assert.equal(events[1].text, 'Hello 🌱'); assert.equal(events[2].model.real_inference, false);
});

test('an interrupted native stream is not labelled complete', async () => {
  const body = new ReadableStream({ start(controller) { controller.enqueue(encoder.encode(`event: message_start\ndata: ${JSON.stringify({ conversation_id: id, run_id: id })}\n\n`)); controller.close(); } });
  await assert.rejects(async () => { for await (const _event of chatEvents(body)) { /* consume */ } }, /interrupted/);
});

test('native configuration fixes IDs, system appearance, no OTA or hardware permissions', async () => {
  const { expo } = JSON.parse(await readFile(new URL('../app.json', import.meta.url), 'utf8'));
  assert.equal(expo.ios.bundleIdentifier, 'eu.onesa.aiplatform'); assert.equal(expo.android.package, 'eu.onesa.aiplatform');
  assert.equal(expo.scheme, 'onesaai'); assert.equal(expo.userInterfaceStyle, 'automatic');
  assert.equal(expo.updates.enabled, false); assert.deepEqual(expo.android.permissions, []);
  assert.ok(expo.android.blockedPermissions.includes('android.permission.RECORD_AUDIO'));
});
