// Source-pinned AI qualification only. Credentials and the resulting cookie
// travel in private process pipes; no screenshots, traces or account changes.
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import identityContext from './oracle_ai_identity_context.cjs';
const {validateIdentity,journalSession}=identityContext;
export {validateIdentity};
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../../onesa-ai-platform-frontend/apps/chat/package.json',import.meta.url));

const configuredContexts=new WeakSet();
const requireValue=(value)=>assert.ok(value,'AI_IDENTITY_BOUNDARY_REFUSED');
export function validateAuthorization(raw,identity,stepUp=false){
 const target=new URL(raw),expected=new URL(identity.issuer);
 requireValue(target.origin===expected.origin&&target.pathname===expected.pathname+'/auth'&&!target.hash&&!target.username&&!target.password);
 const fields=['client_id','redirect_uri','response_type','scope','state','nonce','code_challenge','code_challenge_method'];
 if(stepUp)fields.push('prompt','max_age','acr_values');
 requireValue([...target.searchParams.keys()].length===fields.length&&fields.every(key=>target.searchParams.getAll(key).length===1));
 requireValue(target.searchParams.get('client_id')===identity.client_id&&target.searchParams.get('redirect_uri')===identity.origin+'/api/v1/auth/onesa/callback');
 requireValue(target.searchParams.get('response_type')==='code'&&target.searchParams.get('scope')==='openid email profile onesa'&&target.searchParams.get('code_challenge_method')==='S256');
 requireValue(['state','nonce','code_challenge'].every(key=>/^[A-Za-z0-9_-]{40,128}$/.test(target.searchParams.get(key))));
 if(stepUp)requireValue(target.searchParams.get('prompt')==='login'&&target.searchParams.get('max_age')==='0'&&target.searchParams.get('acr_values')==='urn:onesa:mfa');
 return target;
}

export function validateCallback(raw,identity,authorization){
 const target=new URL(raw),keys=[...target.searchParams.keys()];
 requireValue(target.origin===identity.origin&&target.pathname==='/api/v1/auth/onesa/callback'&&!target.hash&&!target.username&&!target.password);
 requireValue(keys.every(key=>['code','state','iss'].includes(key))&&new Set(keys).size===keys.length);
 requireValue(target.searchParams.get('state')===authorization.searchParams.get('state')&&target.searchParams.getAll('code').length===1&&target.searchParams.get('code').length>0&&target.searchParams.get('code').length<=4096);
 requireValue(!target.searchParams.has('iss')||target.searchParams.get('iss')===identity.issuer);
 return true;
}

export function totp(secret,step){
 requireValue(/^[A-Z2-7]{16,128}$/.test(secret)&&Number.isSafeInteger(step)&&step>=0);
 const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';let bits='';
 for(const char of secret)bits+=alphabet.indexOf(char).toString(2).padStart(5,'0');
 const bytes=[];for(let at=0;at+8<=bits.length;at+=8)bytes.push(parseInt(bits.slice(at,at+8),2));
 const counter=Buffer.alloc(8);counter.writeBigUInt64BE(BigInt(step));
 const digest=createHmac('sha1',Buffer.from(bytes)).update(counter).digest(),offset=digest[digest.length-1]&15;
 return String((digest.readUInt32BE(offset)&0x7fffffff)%1000000).padStart(6,'0');
}

export async function freshCode(secret,{now=Date.now,wait=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds))}={}){
 // A previous browser/role may have consumed this account's current counter.
 // Wait once for a new counter; never retry an invalid factor or use recovery codes.
 const previous=Math.floor(now()/30000),delay=(previous+1)*30000-now()+1000;
 requireValue(delay>0&&delay<=31000);await wait(delay);
 const current=Math.floor(now()/30000);requireValue(current>previous);
 return totp(secret,current);
}

export async function scopeIdentityRequests(context,identity,appBypass){
 const {app,portal}=validateIdentity(identity,'primary');
 requireValue(appBypass===null||appBypass===undefined||identity.environment==='staging'&&typeof appBypass==='string'&&/^[!-~]{1,8192}$/.test(appBypass));
 if(configuredContexts.has(context))return;
 await context.setExtraHTTPHeaders({});
 for(const [origin,secret] of [[app,appBypass],[portal,identity.portal_bypass]]){
  if(!secret)continue;
  const isolated=await context.browser().newContext();
  try{
   const response=await isolated.request.get(origin,{maxRedirects:0,headers:{'x-vercel-protection-bypass':secret,'x-vercel-set-bypass-cookie':'true'}});
   requireValue([200,302,303,307,308].includes(response.status()));
   const location=response.headers().location;
   if(location)requireValue(new URL(location,origin).origin===origin);
   const cookies=(await isolated.cookies(origin)).filter(cookie=>cookie.name==='_vercel_jwt');
   requireValue(cookies.length===1&&cookies[0].secure&&cookies[0].domain.replace(/^\./,'')===new URL(origin).hostname);
   await context.addCookies([{name:'_vercel_jwt',value:cookies[0].value,url:origin,secure:true,httpOnly:true,sameSite:'Lax'}]);
  }finally{await isolated.close();}
 }
 await context.route('**/*',async route=>{
  const request=route.request(),target=new URL(request.url());
  // Do not override Cookie or credential headers: overrides may survive a
  // redirect hop that Playwright does not route again. Host-only cookies scope access.
  if(request.headers()['x-vercel-protection-bypass'])return route.abort();
  if(![app,portal].includes(target.origin))return route.abort();
  if(!['GET','HEAD'].includes(request.method())){
   if(![app,portal].includes(target.origin))return route.abort();
   if(target.origin===portal&&!/^\/api\/v1\/account\/(?:login|interaction\/[A-Za-z0-9_-]{8,128}\/(?:login|continue))$/.test(target.pathname))return route.abort();
  }
  return route.continue();
 });
 configuredContexts.add(context);
}

async function jsonGet(context,origin,path){
 const response=await context.request.get(origin+path,{maxRedirects:0});
 requireValue(response.status()===200);const raw=await response.body();requireValue(raw.length<=65536);
 return JSON.parse(raw.toString('utf8'));
}

function observeIdentityStart(page,identity,frame){
 let rejectBudget,timer;
 const captured=page.waitForResponse(response=>response.request().method()==='POST'&&response.request().frame()===frame&&response.url()===identity.origin+'/api/v1/auth/onesa/start',{timeout:15000}).then(response=>{
  requireValue(response.status()===200);
 });
 const budget=new Promise((_resolve,reject)=>{rejectBudget=reject;timer=setTimeout(()=>reject(new Error('AI_IDENTITY_START_TIMEOUT')),15000);});
 const promise=Promise.race([captured,budget]).finally(()=>clearTimeout(timer));
 promise.catch(()=>{});
 return {promise,close(){clearTimeout(timer);rejectBudget(new Error('AI_IDENTITY_START_CLOSED'));}};
}

export async function signInIdentity(page,context,identity,{actor='primary',appBypass=null,stepUp=false,apiOnly=false,code=freshCode,observe=()=>{}}={}){
 let startObserver;
 try{
  const {app,portal,account}=validateIdentity(identity,actor);
  const {expect}=require('@playwright/test');
  await scopeIdentityRequests(context,identity,appBypass);
  requireValue(new URL(page.url()).origin===app);
  const frame=page.mainFrame();
  const callback=page.waitForRequest(request=>{
   const target=new URL(request.url());return request.isNavigationRequest()&&request.frame()===frame&&request.method()==='GET'&&target.origin===app&&target.pathname==='/api/v1/auth/onesa/callback';
  },{timeout:90000});
  callback.catch(()=>{}); // Register before action; never miss an immediate callback.
  const readAuthorization=async response=>{
   requireValue(response.status()===200);
   return validateAuthorization((await response.json()).authorize_url,identity,stepUp);
  };
  let authorization;
  if(apiOnly){
   requireValue(stepUp===false);
   authorization=await readAuthorization(await context.request.post(app+'/api/v1/auth/onesa/start',{maxRedirects:0,headers:{Origin:app},data:{next:'/',reauthenticate:false}}));
  }else{
   startObserver=observeIdentityStart(page,identity,frame);
   const start=startObserver.promise;
   // Validate the actual browser transaction without retaining a response body
   // across document replacement or changing native request handling.
   const outgoing=page.waitForRequest(request=>{
    const target=new URL(request.url());return request.isNavigationRequest()&&request.frame()===frame&&request.method()==='GET'&&target.origin===portal&&target.pathname===new URL(identity.issuer).pathname+'/auth';
   },{timeout:20000}).then(request=>validateAuthorization(request.url(),identity,stepUp));
   outgoing.catch(()=>{});
   await page.getByRole('button',{name:stepUp?'Confirm administrator sign-in':'Continue with Onesa',exact:true}).click();
   await start; // The same main-frame start POST must have succeeded.
   authorization=await outgoing;
  }
  if(apiOnly)await page.goto(authorization.href);
  await page.waitForURL(url=>url.origin===portal&&/^\/account\/sign-in\/[A-Za-z0-9_-]{8,128}$/.test(url.pathname),{timeout:20000});
  await expect(page.locator('input[name="email"]')).toBeEditable();
  validateIdentity(identity,actor);
  requireValue(new URL(page.url()).origin===portal);
  await page.locator('input[name="email"]').fill(account.email);
  validateIdentity(identity,actor);
  requireValue(new URL(page.url()).origin===portal);
  await page.locator('input[name="password"]').fill(account.password);
  observe('credential_draft_editable');
  const factor=page.locator('input[name="code"]');
  const supplied=await factor.isVisible();
  if(supplied){const factorValue=await code(account.totp_secret);validateIdentity(identity,actor);requireValue(new URL(page.url()).origin===portal);await factor.fill(factorValue);}
  await expect(page.locator('form button').filter({hasText:/^(Continue|Weiter)$/})).toBeEnabled();
  validateIdentity(identity,actor);
  requireValue(new URL(page.url()).origin===portal);
  observe('submission_ready');
  await page.locator('form button').filter({hasText:/^(Continue|Weiter)$/}).click();
  if(!supplied){
   await expect(factor).toBeEditable({timeout:20000});
   requireValue(new URL(page.url()).origin===portal);
   const factorValue=await code(account.totp_secret);validateIdentity(identity,actor);requireValue(new URL(page.url()).origin===portal);await factor.fill(factorValue);
   await page.locator('form button').filter({hasText:/^(Continue|Weiter)$/}).click();
  }
  validateCallback((await callback).url(),identity,authorization);
  await page.waitForURL(url=>url.origin===app&&url.pathname==='/',{timeout:30000});
  if(new URL(page.url()).searchParams.get('identity')==='link_required'){
   // The separately held existing product password proves the immutable local
   // account. Email alone never authorizes linking or replacing its ownership.
   validateIdentity(identity,actor);
   if(apiOnly){
    const linked=await context.request.post(app+'/api/v1/auth/onesa/link',{maxRedirects:0,headers:{Origin:app},data:{email:account.email,current_password:account.local_password}});
    requireValue(linked.status()===200&&(await linked.json()).next==='/');
    await page.goto(app);
   }else{
    await expect(page.getByRole('heading',{name:'Connect your existing AI account',exact:true})).toBeVisible();
   validateIdentity(identity,actor);
   requireValue(new URL(page.url()).origin===app);
    await page.getByLabel('Email',{exact:true}).fill(account.email);
   validateIdentity(identity,actor);
    requireValue(new URL(page.url()).origin===app);
    await page.getByLabel('Existing AI password',{exact:true}).fill(account.local_password);
   validateIdentity(identity,actor);
   requireValue(new URL(page.url()).origin===app);
    await page.getByRole('button',{name:'Connect account',exact:true}).click();
    await page.waitForURL(url=>url.origin===app&&url.pathname==='/'&&!url.search,{timeout:30000});
   }
  }
  requireValue(!new URL(page.url()).search);
  const cookies=await context.cookies(app+'/api/v1/auth/me');
  const sessionCookies=cookies.filter(cookie=>cookie.name==='onesa_session'),csrfCookies=cookies.filter(cookie=>cookie.name==='onesa_csrf');
  requireValue(sessionCookies.length===1&&csrfCookies.length===1);
  const cookie=sessionCookies[0],csrf=csrfCookies[0],instant=Date.now()/1000;
  for(const candidate of [cookie,csrf])requireValue(candidate.domain===new URL(app).hostname&&candidate.path==='/'&&candidate.secure&&candidate.sameSite==='Lax'&&/^[A-Za-z0-9_-]{43}$/.test(candidate.value)&&candidate.expires>instant&&candidate.expires<=instant+86400);
  requireValue(cookie.httpOnly===true&&csrf.httpOnly===false);
  // Record only these observed token hashes before further assertions. Cleanup
  // can retire this exact session without changing other existing sessions.
  journalSession(identity,cookie,csrf.value);
  if(!apiOnly)await expect(page.getByLabel('Message Onesa AI')).toBeVisible({timeout:30000});
  const portalSession=await jsonGet(context,portal,'/api/v1/account/me',identity.portal_bypass);
  requireValue(portalSession.account?.id===account.subject&&portalSession.account.email===account.email&&portalSession.account.emailVerified===true&&portalSession.account.mfaEnrolled===true);
  const session=await jsonGet(context,app,'/api/v1/auth/me');
  requireValue(session.identity_mode==='onesa'&&session.id===account.local_user_id&&session.email===account.email&&session.global_admin===false&&session.administrator===false);
  requireValue(portalSession.account.globalAdmin===false);
  validateIdentity(identity,actor);
  return {schema_version:1,origin:app,issuer:identity.issuer,subject:account.subject,local_user_id:account.local_user_id,csrf:csrf.value,
   cookies:[cookie,csrf].map(value=>Object.fromEntries(['name','value','domain','path','expires','httpOnly','secure','sameSite'].map(key=>[key,value[key]])))};
 }catch{throw new Error('AI_IDENTITY_FLOW_FAILED');}
 finally{startObserver?.close();}
}

export async function acquireIdentity(request){
 validateIdentity(request.identity,request.actor);
 const {chromium}=require('@playwright/test');
 const browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({locale:'en-US'});
  await scopeIdentityRequests(context,request.identity,request.app_bypass);
  const page=await context.newPage();await page.goto(request.identity.origin);
  const result=await signInIdentity(page,context,request.identity,{actor:request.actor,appBypass:request.app_bypass,apiOnly:true});
  await context.close();return result;
 }finally{await browser.close();}
}

export async function signInFixture(context,fixture,index){
 identityContext.validateContext(fixture);
 requireValue(index===0||index===1);
 await scopeIdentityRequests(context,fixture.identity,fixture.bypass);
 const page=await context.newPage();
 try{
  await page.goto(fixture.origin);
  return await signInIdentity(page,context,fixture.identity,{actor:index===0?'primary':'foreign',appBypass:fixture.bypass,apiOnly:true});
 }finally{await page.close();}
}

if(process.argv[1]&&import.meta.url===new URL('file:'+process.argv[1]).href){
 try{
  const raw=fs.readFileSync(0);requireValue(raw.length>0&&raw.length<=65536);
  const request=JSON.parse(raw.toString('utf8'));requireValue(Object.keys(request).sort().join(',')==='actor,app_bypass,identity');
  process.stdout.write(JSON.stringify(await acquireIdentity(request)));
 }catch{process.stderr.write('AI_IDENTITY_SESSION_REFUSED\n');process.exitCode=1;}
}
