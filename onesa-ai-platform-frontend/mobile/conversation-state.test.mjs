import {test} from 'node:test';
import assert from 'node:assert/strict';
import {
  clearSubmittedDraft,
  draftFor,
  moveDraft,
  openConversation,
  withDraft,
} from './conversation-state.mjs';

test('drafts are isolated by conversation and updates do not mutate prior state', () => {
  const empty = new Map();
  const first = withDraft(empty, null, 'unsent message');
  const second = withDraft(first, 'conversation-a', 'another draft');
  assert.equal(draftFor(empty, null), '');
  assert.equal(draftFor(first, null), 'unsent message');
  assert.equal(draftFor(second, 'conversation-a'), 'another draft');
  assert.equal(first.has('conversation-a'), false);
});

test('creating a conversation moves its new-chat draft to the returned ID', () => {
  const original = withDraft(new Map(), null, 'keep this draft');
  const moved = moveDraft(original, null, 'conversation-a');
  assert.equal(draftFor(moved, null), '');
  assert.equal(draftFor(moved, 'conversation-a'), 'keep this draft');
  assert.equal(draftFor(original, null), 'keep this draft');
});

test('successful submission clears only the exact submitted text', () => {
  const submitted = withDraft(new Map(), 'conversation-a', 'sent text');
  assert.equal(clearSubmittedDraft(submitted, 'conversation-a', 'sent text').has('conversation-a'), false);
  const edited = withDraft(submitted, 'conversation-a', 'newer edit');
  assert.equal(clearSubmittedDraft(edited, 'conversation-a', 'sent text').get('conversation-a'), 'newer edit');
});

test('opening a conversation selects it only after detail loading succeeds', async () => {
  const selected = [];
  const detail = {conversation: {id: 'conversation-b'}, messages: []};
  const result = await openConversation(
    'conversation-b',
    async id => {
      assert.equal(id, 'conversation-b');
      return detail;
    },
    (id, value) => selected.push([id, value]),
  );
  assert.equal(result, detail);
  assert.deepEqual(selected, [['conversation-b', detail]]);
});

test('failed conversation loading leaves the current selection untouched', async () => {
  const selected = [['conversation-a', {conversation: {id: 'conversation-a'}}]];
  await assert.rejects(
    openConversation('conversation-b', async () => { throw Error('synthetic load failure'); },
      (id, detail) => selected.push([id, detail])),
    /synthetic load failure/,
  );
  assert.deepEqual(selected, [['conversation-a', {conversation: {id: 'conversation-a'}}]]);
});
