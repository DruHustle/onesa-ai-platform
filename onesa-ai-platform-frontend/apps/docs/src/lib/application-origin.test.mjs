import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveApplicationOrigin } from './application-origin.mjs';

const publicOrigin = 'https://platform.onesa.eu';
const failure = { message: 'Invalid application origin configuration.' };

test('local development defaults to the loopback application', () => {
  assert.equal(resolveApplicationOrigin(), 'http://localhost:3100');
  for (const docsUrl of ['http://localhost:3200', 'http://docs.localhost:3200',
    'http://127.0.0.2:3200', 'http://0.0.0.0:3200', 'http://[::1]:3200', 'http://[::]:3200']) {
    assert.equal(resolveApplicationOrigin({ docsUrl, publicOrigin }), 'http://localhost:3100');
  }
});

test('every hosted context defaults to the supplied pinned application origin', () => {
  for (const context of [{ staticHosting: true }, { accessHosting: true },
    { environment: 'production' }, { environment: 'staging' },
    { docsUrl: 'https://docs.onesa.eu' }, { docsUrl: 'https://preview.example.invalid/' }]) {
    assert.equal(resolveApplicationOrigin({ ...context, publicOrigin }), publicOrigin);
  }
  assert.throws(() => resolveApplicationOrigin({ staticHosting: true }), failure);
});

test('a public docs origin establishes hosted mode even without deployment flags', () => {
  assert.throws(() => resolveApplicationOrigin({ docsUrl: 'https://docs.onesa.eu',
    configured: 'http://localhost:3100', publicOrigin }), failure);
});

test('hosted origins reject loopback addresses and normalized aliases', () => {
  for (const configured of ['https://localhost', 'https://LOCALHOST.', 'https://docs.localhost',
    'https://127.0.0.1', 'https://127.255.0.1', 'https://127.1', 'https://2130706433',
    'https://0.0.0.0', 'https://[::1]', 'https://[0:0:0:0:0:0:0:1]', 'https://[::]']) {
    assert.throws(() => resolveApplicationOrigin({ configured, accessHosting: true, publicOrigin }), failure);
  }
});

test('configured origins reject unsafe protocols, credentials and non-origin URL parts', () => {
  for (const configured of ['http://platform.onesa.eu', 'ftp://platform.onesa.eu',
    'javascript:alert(1)', '//platform.onesa.eu', 'https://user:private@platform.onesa.eu',
    'https://@platform.onesa.eu', 'https://:@platform.onesa.eu',
    'https://platform.onesa.eu?private=value', 'https://platform.onesa.eu?',
    'https://platform.onesa.eu#private', 'https://platform.onesa.eu#',
    'https://platform.onesa.eu/knowledge', 'https://platform.onesa.eu//',
    'https://platform.onesa.eu/./', 'https://platform.onesa.eu/../',
    'https://platform.onesa.eu\\knowledge', ' https://platform.onesa.eu']) {
    assert.throws(() => resolveApplicationOrigin({ configured, staticHosting: true, publicOrigin }), failure);
  }
});

test('docs origins are validated without exposing configured credentials', () => {
  for (const docsUrl of ['invalid', 'ftp://docs.onesa.eu', 'https://user:private@docs.onesa.eu',
    'https://docs.onesa.eu/docs', 'https://docs.onesa.eu?private=value', 'https://docs.onesa.eu#private']) {
    assert.throws(() => resolveApplicationOrigin({ docsUrl, publicOrigin }), failure);
  }
});

test('valid HTTPS overrides normalize their optional trailing slash', () => {
  assert.equal(resolveApplicationOrigin({ configured: 'https://preview.example.invalid/',
    environment: 'staging', publicOrigin }), 'https://preview.example.invalid');
  assert.equal(resolveApplicationOrigin({ configured: 'https://platform.onesa.eu:8443/',
    staticHosting: true, publicOrigin }), 'https://platform.onesa.eu:8443');
  for (const configured of ['https://127.example.invalid', 'https://localhost.example.invalid']) {
    assert.equal(resolveApplicationOrigin({ configured, accessHosting: true, publicOrigin }), configured);
  }
});

test('local configured origins retain explicit loopback ports', () => {
  assert.equal(resolveApplicationOrigin({ configured: 'http://localhost:3199/' }),
    'http://localhost:3199');
  assert.equal(resolveApplicationOrigin({ configured: 'http://[::1]:3199',
    docsUrl: 'http://127.0.0.1:3200', environment: 'development', publicOrigin }),
  'http://[::1]:3199');
  assert.throws(() => resolveApplicationOrigin({ configured: 'http://localhost:3199/knowledge' }), failure);
});
