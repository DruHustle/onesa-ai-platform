import assert from 'node:assert/strict';
import test from 'node:test';
import {validateIdentity,validateAuthorization,validateCallback,totp,freshCode,scopeIdentityRequests,signInIdentity} from './oracle_ai_identity_browser.mjs';
import contextContract from './oracle_ai_identity_context.cjs';

function identity(){
 const account={subject:'11111111-1111-4111-8111-111111111111',local_user_id:'22222222-2222-4222-8222-222222222222',email:'primary@example.test',password:'central-synthetic-password',local_password:'separate-local-password',totp_secret:'JBSWY3DPEHPK3PXP'};
 return {profile:'shared-identity-v1',environment:'staging',origin:'https://onesa-ai-platform-git-staging-fixture.vercel.app',issuer:'https://onesa-company-portal-fixture.vercel.app/api/v1/identity',client_id:'onesa-ai-staging-client',candidate_commit:'a'.repeat(40),operation_id:'55555555-5555-4555-8555-555555555555',expires_at:new Date(Date.now()+300000).toISOString(),accounts:{primary:account,foreign:{...account,subject:'33333333-3333-4333-8333-333333333333',local_user_id:'44444444-4444-4444-8444-444444444444',email:'foreign@example.test'}},portal_bypass:'',session_journal:'/private/output/identity-sessions.jsonl'};
}
function authorization(value){
 const url=new URL(value.issuer+'/auth');
 for(const [key,item] of Object.entries({client_id:value.client_id,redirect_uri:value.origin+'/api/v1/auth/onesa/callback',response_type:'code',scope:'openid email profile onesa',state:'s'.repeat(43),nonce:'n'.repeat(43),code_challenge:'c'.repeat(43),code_challenge_method:'S256'}))url.searchParams.set(key,item);
 return url;
}

test('source, exact slot, native account mapping and separate password proof are required',()=>{
 const value=identity();
 for(const actor of ['primary','foreign'])assert.equal(validateIdentity(value,actor).app,value.origin);
 for(const change of [v=>v.origin='https://ai-api-staging.onesa.eu',v=>v.environment='production',v=>v.issuer='https://foreign.example.test/api/v1/identity',v=>delete v.accounts.primary.local_password,v=>v.accounts.foreign.local_user_id=v.accounts.primary.local_user_id,v=>v.candidate_commit='unbound',v=>v.expires_at=new Date(Date.now()-1000).toISOString()]){
  const changed=structuredClone(value);change(changed);assert.throws(()=>validateIdentity(changed));
 }
});

test('fixture context cannot swap a normal user, operation, source or production credential',()=>{
 const value=identity(),users=['primary','foreign'].map(actor=>{const account=value.accounts[actor];return {id:account.local_user_id,email:account.email,password:account.password};});
 const context={identity:value,origin:value.origin,environment:value.environment,operation_id:value.operation_id,binding:{candidate_commit:value.candidate_commit},users};
 assert.equal(contextContract.validateContext(context),value);
 for(const mutate of [c=>c.users.reverse(),c=>c.operation_id='66666666-6666-4666-8666-666666666666',c=>c.binding.candidate_commit='b'.repeat(40),c=>c.identity.environment='production']){
  const changed=structuredClone(context);mutate(changed);assert.throws(()=>contextContract.validateContext(changed));
 }
});

test('actual S256 authorization requires exact issuer callback nonce and state',()=>{
 const value=identity(),url=authorization(value);assert.equal(validateAuthorization(url.href,value).href,url.href);
 for(const [key,item] of [['client_id','unbound-client'],['redirect_uri','https://foreign.example.test/callback'],['code_challenge_method','plain'],['response_type','token'],['scope','openid']]){
  const changed=new URL(url);changed.searchParams.set(key,item);assert.throws(()=>validateAuthorization(changed.href,value));
 }
 const duplicate=new URL(url);duplicate.searchParams.append('state','s'.repeat(43));assert.throws(()=>validateAuthorization(duplicate.href,value));
 assert.throws(()=>validateAuthorization(url.href.replace('onesa-company-portal-fixture.vercel.app','foreign.example.test'),value));
});

test('callback cannot qualify another browser transaction or issuer',()=>{
 const value=identity(),auth=authorization(value),callback=new URL(value.origin+'/api/v1/auth/onesa/callback');
 callback.searchParams.set('code','synthetic-code');callback.searchParams.set('state',auth.searchParams.get('state'));callback.searchParams.set('iss',value.issuer);
 assert.equal(validateCallback(callback.href,value,auth),true);
 for(const [key,item] of [['state','foreign-state'],['iss','https://foreign.example.test/api/v1/identity'],['error','access_denied']]){
  const changed=new URL(callback);changed.searchParams.set(key,item);assert.throws(()=>validateCallback(changed.href,value,auth));
 }
});

test('authenticator waits for one new real counter and never retries factors',async()=>{
 assert.equal(totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ',1),'287082');
 let current=29500;const waits=[];
 const code=await freshCode('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ',{now:()=>current,wait:async milliseconds=>{waits.push(milliseconds);current+=milliseconds;}});
 assert.equal(code,'287082');assert.deepEqual(waits,[1500]);
});

test('automation access is isolated to exact-origin no-redirect cookie handshakes',async()=>{
 const value=identity();value.portal_bypass='synthetic-portal-bypass';
 const requests=[],added=[];let route;
 const context={setExtraHTTPHeaders:async headers=>assert.deepEqual(headers,{}),addCookies:async cookies=>added.push(...cookies),route:async(_pattern,callback)=>{route=callback;},browser:()=>({newContext:async()=>{
  let destination;
  return {request:{get:async(origin,options)=>{destination=origin;requests.push([origin,options]);return {status:()=>307,headers:()=>({location:'/same-origin'})};}},cookies:async()=>[{name:'_vercel_jwt',value:'synthetic-cookie',secure:true,domain:new URL(destination).hostname}],close:async()=>{}};
 }})};
 await scopeIdentityRequests(context,value,'synthetic-app-bypass');
 assert.equal(requests.length,2);assert.ok(requests.every(([,options])=>options.maxRedirects===0));
 assert.deepEqual(added.map(cookie=>cookie.url),[value.origin,new URL(value.issuer).origin]);
 assert.ok(added.every(cookie=>!Object.hasOwn(cookie,'domain')&&cookie.httpOnly&&cookie.secure));
 for(const [url,method,headers] of [['https://foreign.example.test/script.js','GET',{}],[new URL(value.issuer).origin+'/api/v1/account/admin','POST',{}],[value.origin+'/','GET',{'x-vercel-protection-bypass':'must-not-travel'}]]){
  let aborted=false;
  await route({request:()=>({url:()=>url,headers:()=>headers,method:()=>method}),continue:async()=>assert.fail('Forbidden request continued'),abort:async()=>{aborted=true;}});
  assert.equal(aborted,true);
 }
});

test('a foreign bypass redirect is refused before its target is visited',async()=>{
 const value=identity();let added=false,closed=false;
 const context={setExtraHTTPHeaders:async()=>{},addCookies:async()=>{added=true;},route:async()=>assert.fail(),browser:()=>({newContext:async()=>({request:{get:async(_origin,options)=>{assert.equal(options.maxRedirects,0);return {status:()=>307,headers:()=>({location:'https://foreign.example.test/'})};}},close:async()=>{closed=true;}})})};
 await assert.rejects(scopeIdentityRequests(context,value,'synthetic-bypass'));assert.equal(added,false);assert.equal(closed,true);
});

test('UI identity validates the actual browser transaction when its response body is unavailable',async t=>{
 for(const mutation of ['none','start_status','start_frame','start_method','client','method','frame','non_navigation','foreign_origin'])await t.test(mutation,async()=>{
  const value=identity(),frame={},observers={};let bodyReads=0,portalObservations=0,beforeClick;
  const response={url:()=>value.origin+'/api/v1/auth/onesa/start',request:()=>({method:()=>mutation==='start_method'?'GET':'POST',frame:()=>mutation==='start_frame'?{}:frame}),status:()=>mutation==='start_status'?503:200,
   async json(){bodyReads++;throw new Error('Response body was discarded during document replacement');}};
  const page={url:()=>value.origin,mainFrame:()=>frame,
   async route(){assert.fail('The protocol observer must not install another request route');},
   waitForResponse(predicate,options){assert.equal(options.timeout,15000);return new Promise((resolve,reject)=>{observers.start={predicate,resolve,reject};});},
   waitForRequest(predicate,options){const key=options.timeout===90000?'callback':'authorization';assert.equal(options.timeout,key==='callback'?90000:20000);return new Promise((resolve,reject)=>{observers[key]={predicate,resolve,reject};});},
   getByRole(role,options){assert.equal(role,'button');assert.deepEqual(options,{name:'Continue with Onesa',exact:true});return {async click(){
    beforeClick={start:!!observers.start,authorization:!!observers.authorization,callback:!!observers.callback};assert(observers.start);
    if(observers.start.predicate(response))observers.start.resolve(response);else observers.start.reject(new Error('Synthetic start observer timeout'));
    const destination=authorization(value);
    if(mutation==='client')destination.searchParams.set('client_id','foreign-client');
    if(mutation==='foreign_origin')destination.hostname='foreign.example.test';
    const request={url:()=>destination.href,method:()=>mutation==='method'?'POST':'GET',frame:()=>mutation==='frame'?{}:frame,isNavigationRequest:()=>mutation!=='non_navigation'};
    if(observers.authorization){if(observers.authorization.predicate(request))observers.authorization.resolve(request);else observers.authorization.reject(new Error('Synthetic authorization observer timeout'));}
    if(observers.callback){
     const callback={url:()=>value.origin+'/api/v1/auth/onesa/callback',method:()=>'GET',frame:()=>frame,isNavigationRequest:()=>true};
     assert(observers.callback.predicate(callback));
     for(const changed of [{method:()=>'POST'},{frame:()=>({})},{isNavigationRequest:()=>false}])assert(!observers.callback.predicate({...callback,...changed}));
    }
   }};},
   async waitForURL(){portalObservations++;throw new Error('Synthetic observer stops before Portal credentials');},
  };
  const context={async setExtraHTTPHeaders(headers){assert.deepEqual(headers,{});},async route(){}};
  await assert.rejects(signInIdentity(page,context,value),{message:'AI_IDENTITY_FLOW_FAILED'});
  assert.equal(bodyReads,0,'UI qualification must not read a discarded response body');
  assert.deepEqual(beforeClick,{start:true,authorization:true,callback:true});assert.equal(portalObservations,mutation==='none'?1:0);
 });
});

test('API-only identity keeps its original request and never installs a navigation hold',async()=>{
 const value=identity(),expected=authorization(value).href,events=[],frame={};let posts=0,callbackRegistered=false;
 const context={async setExtraHTTPHeaders(headers){assert.deepEqual(headers,{});},async route(){},request:{async post(url,options){
  posts++;assert(callbackRegistered);assert.equal(url,value.origin+'/api/v1/auth/onesa/start');
  assert.deepEqual(options,{maxRedirects:0,headers:{Origin:value.origin},data:{next:'/',reauthenticate:false}});events.push('post');
  return {status:()=>200,async json(){events.push('body');return {authorize_url:expected};}};
 }}};
 const page={url:()=>value.origin,mainFrame:()=>frame,async route(){assert.fail('API-only must not install a page route');},waitForResponse(){assert.fail('API-only must not observe a browser start response');},
  waitForRequest(_predicate,options){assert.equal(options.timeout,90000);callbackRegistered=true;return new Promise(()=>{});},async goto(url){assert.equal(url,expected);events.push('navigation');},
  async waitForURL(){events.push('portal-observation');throw new Error('Synthetic observer stops before Portal credentials');},
 };
 await assert.rejects(signInIdentity(page,context,value,{apiOnly:true}),{message:'AI_IDENTITY_FLOW_FAILED'});
 assert.equal(posts,1);assert.deepEqual(events,['post','body','navigation','portal-observation']);
});
