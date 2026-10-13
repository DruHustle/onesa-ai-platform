import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import gateway from '../../infra/cloudflare-docs/worker.mjs';
let pair,jwk;
const audience='a'.repeat(64);
const env={CF_ACCESS_TEAM_DOMAIN:'onesa-test.cloudflareaccess.com',CF_ACCESS_AUDIENCES:JSON.stringify([audience]),CF_ACCESS_ENGINEERING_EMAILS:'["engineer@example.invalid"]',CF_ACCESS_ALLOWED_HOSTS:'["onesa-test.pages.dev","*.onesa-test.pages.dev","engineering.docs.onesa.eu"]'};
const encoded=value=>Buffer.from(JSON.stringify(value)).toString('base64url');
before(async()=>{pair=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);jwk={...await crypto.subtle.exportKey('jwk',pair.publicKey),kid:'synthetic-kid',alg:'RS256'};});
async function token(changes={}){const now=Math.floor(Date.now()/1000);const text=encoded({alg:'RS256',kid:jwk.kid})+'.'+encoded({iss:'https://'+env.CF_ACCESS_TEAM_DOMAIN,aud:[audience],email:'engineer@example.invalid',sub:'synthetic-engineer',iat:now-10,exp:now+300,...changes});return text+'.'+Buffer.from(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',pair.privateKey,new TextEncoder().encode(text))).toString('base64url');}
async function call(path,credential,changes={},options={}){let assets=0;const original=globalThis.fetch;globalThis.fetch=async url=>{assert.equal(url,'https://'+env.CF_ACCESS_TEAM_DOMAIN+'/cdn-cgi/access/certs');return Response.json({keys:[jwk]});};try{const response=await gateway.fetch(new Request('https://'+(options.host||'onesa-test.pages.dev')+path,{headers:options.cookie?{cookie:'CF_Authorization='+credential}:credential?{'cf-access-jwt-assertion':credential}:{},method:options.method||'GET'}),{...env,...changes,ASSETS:{fetch:()=>{assets++;if(options.assetError)throw new Error(options.assetError);return new Response('synthetic engineering artifact');}}});return {response,assets};}finally{globalThis.fetch=original;}}
test('anonymous direct documents, search indexes, diagrams and manuals never reach assets',async()=>{for(const path of ['/docs','/generated/retrieval.json','/assets/js/main.js','/manuals/private.pdf','/sitemap.xml']){const {response,assets}=await call(path);assert.equal(response.status,401);assert.equal(assets,0);assert.equal(response.headers.get('cache-control'),'private, no-store');}});
test('signed approved engineering identity can read private assets',async()=>{const {response,assets}=await call('/manuals/engineering.pdf',await token());assert.equal(response.status,200);assert.equal(assets,1);assert.equal(response.headers.get('x-robots-tag'),'noindex, nofollow, noarchive');});
test('normal users, wrong audience, wrong issuer, expired and future tokens are denied',async()=>{for(const change of [{email:'ordinary@example.invalid'},{aud:['b'.repeat(64)]},{iss:'https://other.cloudflareaccess.com'},{exp:1},{iat:Math.floor(Date.now()/1000)+3600},{sub:''}]){const {response,assets}=await call('/database',await token(change));assert.equal(response.status,401);assert.equal(assets,0);}});
test('forged assertion cannot authenticate with a valid-looking unsigned payload',async()=>{const jwt=await token();const parts=jwt.split('.');parts[2]='a'.repeat(parts[2].length);const {response,assets}=await call('/generated/database.json',parts.join('.'));assert.equal(response.status,401);assert.equal(assets,0);});
test('missing or invalid runtime Access configuration fails closed',async()=>{for(const change of [{CF_ACCESS_TEAM_DOMAIN:''},{CF_ACCESS_AUDIENCES:'[]'},{CF_ACCESS_ENGINEERING_EMAILS:'[]'},{CF_ACCESS_ALLOWED_HOSTS:'["*.evil.test"]'}]){const {response,assets}=await call('/docs',await token(),change);assert.equal(response.status,401);assert.equal(assets,0);}});
test('unknown direct origin is rejected despite a signed identity',async()=>{const {response,assets}=await call('/docs',await token(),{CF_ACCESS_ALLOWED_HOSTS:'["engineering.docs.onesa.eu"]'});assert.equal(response.status,401);assert.equal(assets,0);});
test('malformed and oversized assertions never expose assets',async()=>{for(const jwt of ['bad.token','x'.repeat(9000),'e30.e30.invalid']){const {response,assets}=await call('/assets/css/styles.css',jwt);assert.equal(response.status,401);assert.equal(assets,0);}});
test('origin, commit preview, branch alias and custom hostname all require authorized identity',async()=>{const jwt=await token();for(const host of ['onesa-test.pages.dev','123abc.onesa-test.pages.dev','dev.onesa-test.pages.dev','engineering.docs.onesa.eu']){for(const path of ['/docs','/generated/search.json','/manuals/engineering.pdf']){const anonymous=await call(path,undefined,{}, {host});assert.equal(anonymous.response.status,401);assert.equal(anonymous.assets,0);const allowed=await call(path,jwt,{}, {host});assert.equal(allowed.response.status,200);assert.equal(allowed.assets,1);}}});
test('signed Access cookie works while cookie forgery and hostname suffix tricks fail',async()=>{const jwt=await token();const approved=await call('/docs',jwt,{}, {cookie:true});assert.equal(approved.response.status,200);assert.equal(approved.assets,1);const forged=await call('/docs','e30.e30.invalid',{}, {cookie:true});assert.equal(forged.response.status,401);assert.equal(forged.assets,0);for(const host of ['onesa-test.pages.dev.evil.invalid','evilonesa-test.pages.dev','engineering.docs.onesa.eu.evil.invalid']){const denied=await call('/docs',jwt,{}, {host});assert.equal(denied.response.status,401);assert.equal(denied.assets,0);}});
test('write methods cannot reach static assets even with approved identity',async()=>{for(const method of ['POST','PUT','DELETE']){const {response,assets}=await call('/assistant',await token(),{}, {method});assert.equal(response.status,405);assert.equal(assets,0);assert.equal(response.headers.get('cache-control'),'private, no-store');}});

test('denial diagnostics never disclose assertions or provider error bodies',async()=>{
 const original=console.warn,logged=[];console.warn=value=>logged.push(value);
 const hostile='SYNTHETIC_ERROR_BODY_DO_NOT_LOG';
 try{
  const invalid=await call('/docs','e30.e30.invalid');assert.equal(invalid.response.status,401);
  const failure=await call('/docs',await token(),{}, {assetError:hostile});assert.equal(failure.response.status,401);
  assert.equal(await failure.response.text(),'Authorized engineering access required.');
  assert.equal(logged.length,2);assert.ok(logged.every(value=>JSON.parse(value).event==='engineering_access_denied'));
  assert.ok(!logged.join('').includes(hostile));assert.ok(!logged.join('').includes('e30.e30.invalid'));
 }finally{console.warn=original;}
});

test('signing-key redirects fail closed without following an untrusted destination',async()=>{
 const savedJwk=jwk,original=globalThis.fetch;let assets=0,fetches=0;
 jwk={...jwk,kid:'uncached-redirect-test'};
 try{
  const credential=await token();
  globalThis.fetch=async(url,options)=>{fetches++;assert.equal(url,'https://'+env.CF_ACCESS_TEAM_DOMAIN+'/cdn-cgi/access/certs');assert.equal(options.redirect,'manual');return new Response(null,{status:302,headers:{Location:'https://untrusted.example.invalid/keys'}});};
  const response=await gateway.fetch(new Request('https://onesa-test.pages.dev/docs',{headers:{'cf-access-jwt-assertion':credential}}),{...env,ASSETS:{fetch:()=>{assets++;return new Response('must remain private');}}});
  assert.equal(response.status,401);assert.equal(assets,0);assert.equal(fetches,1);
 }finally{jwk=savedJwk;globalThis.fetch=original;}
});
