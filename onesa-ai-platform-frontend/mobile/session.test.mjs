import {test} from 'node:test';
import assert from 'node:assert/strict';
import {signIn, signOut, CALLBACK, AUTH} from './session.mjs';
const state = 'native_' + 'A'.repeat(43);
const verifier = 'V'.repeat(64);
const challenge = 'C'.repeat(43);
const url = 'https://auth.onesa.eu/authorize?state=' + state +
  '&code_challenge=' + challenge + '&code_challenge_method=S256';
const createPkce = async () => ({verifier, challenge});
for (const [scenario, value] of Object.entries({correct:CALLBACK+'?state='+state+'&code=fixture', stale:CALLBACK+'?state=wrong&code=fixture', foreign:'wrong://account/callback?state='+state+'&code=fixture', duplicate:CALLBACK+'?state='+state+'&code=fixture&code=other', cancelled:CALLBACK+'?state='+state+'&error=cancelled'})) {
  test(scenario + ' system-browser return', async () => {
    const paths=[];
    const api=async (path,opts)=>{
      paths.push(path);
      if(path===AUTH+'/start') {
        assert.deepEqual(opts.body,{mobile:true,code_challenge:challenge});
        return {authorize_url:url};
      }
      assert.deepEqual(opts.body,{state,code:'fixture',code_verifier:verifier});
      return {ok:true};
    };
    const result=signIn(async(authorize,back)=>{assert.equal(authorize,url);assert.equal(back,CALLBACK);return {type:'success',url:value};},api,createPkce);
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

test('native sign-in refuses an invalid PKCE pair before starting authorization', async () => {
  let calls = 0;
  await assert.rejects(
    signIn(async () => { throw Error('must not open browser'); }, async () => { calls += 1; }, async () => ({
      verifier: 'short',
      challenge,
    })),
    /Secure sign-in is unavailable/,
  );
  assert.equal(calls, 0);
});
