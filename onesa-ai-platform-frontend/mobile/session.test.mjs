import {test} from 'node:test';
import assert from 'node:assert/strict';
import {signIn, signOut, CALLBACK, AUTH} from './session.mjs';
const state = 'native_' + 'A'.repeat(43);
const url = 'https://auth.onesa.eu/authorize?state=' + state + '&code_challenge_method=S256';
for (const [scenario, value] of Object.entries({correct:CALLBACK+'?state='+state+'&code=fixture', stale:CALLBACK+'?state=wrong&code=fixture', foreign:'wrong://account/callback?state='+state+'&code=fixture', duplicate:CALLBACK+'?state='+state+'&code=fixture&code=other', cancelled:CALLBACK+'?state='+state+'&error=cancelled'})) {
  test(scenario + ' system-browser return', async () => {
    const paths=[];
    const api=async (path,opts)=>{
      paths.push(path);
      if(path===AUTH+'/start') return {authorize_url:url};
      assert.deepEqual(opts.body,{state,code:'fixture'});
      return {ok:true};
    };
    const result=signIn(async(authorize,back)=>{assert.equal(authorize,url);assert.equal(back,CALLBACK);return {type:'success',url:value};},api);
    if(scenario==='correct'){assert.deepEqual(await result,{ok:true});assert.equal(paths.length,2);}
    else {await assert.rejects(result);assert.equal(paths.length,1);}
  });
}

for (const failed of [false, true]) {
  test('sign-out clears native data when remote revocation ' + (failed ? 'fails' : 'succeeds'), async () => {
    const events=[];
    const remote = async (path, options) => {
      assert.equal(path, '/auth/logout');
      assert.deepEqual(options, {method:'POST',csrf:'session-csrf'});
      events.push('remote');
      if (failed) throw Error('Central sign-out unconfirmed');
    };
    const signout=signOut('session-csrf', async () => {events.push('erase');}, () => events.push('reset'), remote);
    if (failed) await assert.rejects(signout, /Central sign-out unconfirmed/);
    else await signout;
    assert.deepEqual(events, ['remote','erase','reset']);
  });
}

test('sign-out clears private view even when secure-store erasure fails', async () => {
  const events=[];
  await assert.rejects(signOut('csrf', async () => {events.push('erase'); throw Error('store error');}, () => events.push('reset'), async () => {events.push('remote');}), /store error/);
  assert.deepEqual(events, ['remote','erase','reset']);
});


import {
  clearSubmittedDraft,
  draftFor,
  moveDraft,
  openConversation,
  withDraft,
} from './conversation-state.mjs';

test('conversation drafts stay isolated and restore when switching conversations', () => {
  let drafts = new Map();
  drafts = withDraft(drafts, 'conversation-a', 'draft A');
  drafts = withDraft(drafts, 'conversation-b', 'draft B');
  assert.equal(draftFor(drafts, 'conversation-a'), 'draft A');
  assert.equal(draftFor(drafts, 'conversation-b'), 'draft B');
  assert.equal(draftFor(drafts, 'conversation-c'), '');
});

test('a failed conversation load leaves the visible conversation target unchanged', async () => {
  let target = 'conversation-a';
  let selected = {conversation: {id: 'conversation-a'}};
  await assert.rejects(
    openConversation(
      'conversation-b',
      async () => { throw Error('Conversation unavailable'); },
      (id, detail) => { target = id; selected = detail; },
    ),
    /Conversation unavailable/,
  );
  assert.equal(target, 'conversation-a');
  assert.deepEqual(selected, {conversation: {id: 'conversation-a'}});
});

test('a successful conversation load updates target and visible detail together', async () => {
  let target = 'conversation-a';
  let selected = {conversation: {id: 'conversation-a'}};
  const detail = {conversation: {id: 'conversation-b'}, messages: []};
  await openConversation(
    'conversation-b',
    async id => { assert.equal(id, 'conversation-b'); return detail; },
    (id, value) => { target = id; selected = value; },
  );
  assert.equal(target, 'conversation-b');
  assert.equal(selected, detail);
});

test('creating a conversation moves the latest in-flight new-chat draft', () => {
  let drafts = withDraft(new Map(), null, 'first text');
  drafts = withDraft(drafts, null, 'edited while create request is pending');
  drafts = moveDraft(drafts, null, 'conversation-new');
  assert.equal(draftFor(drafts, null), '');
  assert.equal(draftFor(drafts, 'conversation-new'), 'edited while create request is pending');
});

test('successful send clears only the submitted snapshot, preserving concurrent edits', () => {
  const submitted = 'first message';
  let drafts = withDraft(new Map(), 'conversation-a', submitted);
  const newer = withDraft(drafts, 'conversation-a', 'typed while sending');
  assert.equal(clearSubmittedDraft(newer, 'conversation-a', submitted), newer);
  const cleared = clearSubmittedDraft(drafts, 'conversation-a', submitted);
  assert.equal(draftFor(cleared, 'conversation-a'), '');
  assert.equal(draftFor(drafts, 'conversation-a'), submitted);
});

test('failed send retains its draft because no success-clear transition occurs', () => {
  const drafts = withDraft(new Map(), 'conversation-a', 'retry this request');
  assert.equal(draftFor(drafts, 'conversation-a'), 'retry this request');
});
