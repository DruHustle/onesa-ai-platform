import test from 'node:test';
import assert from 'node:assert/strict';
import { SessionStore } from '../src/session-store.ts';

const credential = {
  access_token: 'synthetic_native_' + 'a'.repeat(64), expires_at: '2099-01-01T00:00:00Z',
  user: { id: '765fd0f2-9f1b-48a6-bf1e-b5887b871458', email: 'native@example.invalid', display_name: 'Synthetic user' },
};

test('a delayed expiry clear cannot delete a newer successful sign-in', async () => {
  let value = 'old session', finishDelete;
  const store = new SessionStore({
    read: async () => value,
    write: async next => { value = next; },
    remove: () => new Promise(resolve => { finishDelete = () => { value = null; resolve(); }; }),
  });
  const clearing = store.clear();
  await Promise.resolve();
  const signingIn = store.save(credential);
  await Promise.resolve();
  assert.equal(value, 'old session');
  finishDelete();
  await Promise.all([clearing, signingIn]);
  assert.deepEqual(await store.restore(), credential);
});

test('invalid restored data is deleted before a later credential is saved', async () => {
  let value = 'invalid old session', finishRead;
  const store = new SessionStore({
    read: () => new Promise(resolve => { finishRead = () => resolve(value); }),
    write: async next => { value = next; },
    remove: async () => { value = null; },
  });
  const restoring = store.restore();
  await Promise.resolve();
  const signingIn = store.save(credential);
  finishRead();
  assert.equal(await restoring, null);
  await signingIn;
  assert.deepEqual(JSON.parse(value), credential);
});

test('storage failures remain visible and do not deadlock later cleanup', async () => {
  let failed = false, removed = false;
  const store = new SessionStore({
    read: async () => null,
    write: async () => { throw new Error('synthetic keychain failure'); },
    remove: async () => { removed = true; },
  });
  await store.save(credential).catch(error => { failed = error.message === 'synthetic keychain failure'; });
  await store.clear();
  assert.equal(failed, true); assert.equal(removed, true);
});
