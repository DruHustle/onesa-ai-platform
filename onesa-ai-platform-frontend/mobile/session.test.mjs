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
