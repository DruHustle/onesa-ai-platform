import {createHash} from 'node:crypto';
// Protected-Docs GET observations only. No identity export or release authority.
import {verifyNativePublicAssets,guardOwnedHttp,nativeGet,ownedAuditPage,cleanupOwnedTargets} from './native-owner.mjs';
import {validateProtectedDocumentation} from './internal-acceptance.mjs';

export function protectedDocsOrigin(value,environment){
 const url=new URL(value);
 if(url.protocol!=='https:'||url.port||url.username||url.password||url.search||url.hash||url.pathname!=='/')throw Error('EXACT_PROTECTED_DOCS_ORIGIN_REQUIRED');
 if(environment==='production'&&url.href==='https://docs.engineering.onesa.eu/')return url.origin;
 if(environment==='staging'&&/^[a-f0-9]{8}\.onesa-engineering-docs\.pages\.dev$/.test(url.hostname))return url.origin;
 throw Error('ONLY_EXISTING_PROTECTED_DOCS_PROJECT_SUPPORTED');
}
export function protectedHeaders(headers){
 if(!headers||typeof headers['cache-control']!=='string'||!headers['cache-control'].split(',').map(x=>x.trim().toLowerCase()).includes('no-store')||typeof headers['x-robots-tag']!=='string'||!headers['x-robots-tag'].split(',').map(x=>x.trim().toLowerCase()).includes('noindex')||headers['x-content-type-options']!=='nosniff')throw Error('PROTECTED_BYTES_MUST_REMAIN_NOSTORE_NOINDEX_NOSNIFF');
 return {cache_control:headers['cache-control'],robots:headers['x-robots-tag'],nosniff:headers['x-content-type-options']};
}
export async function verifyProtectedAssets(get,origin,assets){
 const security=[];
 const result=await verifyNativePublicAssets(async value=>{
  const response=await get(value);
  if(response.status()!==200)throw Error('GENUINE_APPROVED_ENGINEERING_SESSION_REQUIRED');
  security.push({route:new URL(value).pathname,...protectedHeaders(response.headers())});
  return response;
 },origin,assets);
 return {...result,asset_security:security.sort((a,b)=>a.route.localeCompare(b.route))};
}
export async function verifyAnonymousProtectedAssets(get,origins,assets,teamOrigin){
 if(typeof get!=='function'||!Array.isArray(origins)||origins.length!==3||new Set(origins).size!==3||!origins.includes('https://docs.engineering.onesa.eu')||!origins.includes('https://onesa-engineering-docs.pages.dev'))throw Error('THREE_EXISTING_PROTECTED_HOSTS_REQUIRED');
 const preview=origins.find(x=>x!=='https://docs.engineering.onesa.eu'&&x!=='https://onesa-engineering-docs.pages.dev');
 if(protectedDocsOrigin(preview+'/','staging')!==preview)throw Error('EXACT_PREVIEW_ALIAS_REQUIRED');
 const team=new URL(teamOrigin);
 if(team.protocol!=='https:'||team.port||team.username||team.password||team.pathname!=='/'||team.search||team.hash||!/^[a-z0-9][a-z0-9-]*\.cloudflareaccess\.com$/.test(team.hostname)||team.origin!==teamOrigin)throw Error('EXACT_EXISTING_ACCESS_TEAM_REQUIRED');
 if(!Array.isArray(assets)||assets.length<100||assets.length>20000||new Set(assets.map(x=>x.route)).size!==assets.length)throw Error('COMPLETE_BOUND_PROTECTED_ASSETS_REQUIRED');
 for(const asset of assets)if(typeof asset.route!=='string'||!asset.route.startsWith('/')||asset.route.startsWith('//')||/[?#\\]/.test(asset.route))throw Error('EXACT_PROTECTED_ASSET_PATH_REQUIRED');
 const pending=origins.flatMap(origin=>assets.map(asset=>({origin,route:asset.route}))),results=[];let next=0,failed=false,firstFailure;
 async function worker(){while(!failed){
  const index=next++;if(index>=pending.length)return;
  const item=pending[index];
  try{
   // The owned unauthenticated request context must honor these fixed options;
   // no owner session, authorization header, redirect or retry is supplied.
   const response=await get(item.origin+item.route,{maxRedirects:0,maxRetries:0,timeout:15000});
   const status=response.status();
   if(![302,401,403].includes(status))throw Error('ANONYMOUS_PROTECTED_CONTENT_OR_MISSING_GATE');
   let redirectOrigin=null;
   if(status===302){
    const redirect=new URL(response.headers().location);
    if(redirect.origin!==teamOrigin||redirect.username||redirect.password||!redirect.pathname.startsWith('/cdn-cgi/access/login/'))throw Error('ONLY_EXISTING_ACCESS_LOGIN_REDIRECT_ALLOWED');
    redirectOrigin=redirect.origin;
   }
   results.push({...item,http_status:status,followed_redirect:false,redirect_origin:redirectOrigin});
  }catch(error){failed=true;firstFailure??=error;throw error;}
 }}
 await Promise.allSettled(Array.from({length:4},worker));
 if(failed)throw firstFailure;
 if(results.length!==pending.length)throw Error('ALL_PROTECTED_HOST_AND_ASSET_DENIALS_REQUIRED');
 return results.sort((a,b)=>(a.origin+a.route).localeCompare(b.origin+b.route));
}

export async function verifyProtectedRollback(get,rollback){
 if(!rollback||Object.keys(rollback).sort().join()!==['deployment_id','source','index_sha256','provenance_sha256'].sort().join()||!/^[a-f0-9-]{36}$/.test(rollback.deployment_id)||!/^[a-f0-9]{40}$/.test(rollback.source)||!['index_sha256','provenance_sha256'].every(k=>/^[a-f0-9]{64}$/.test(rollback[k])))throw Error('EXACT_RETAINED_PRIVATE_STATIC_ROLLBACK_REQUIRED');
 const origin='https://docs.engineering.onesa.eu';
 for(const [path,key] of [['/','index_sha256'],['/generated/provenance.json','provenance_sha256']]){
  const response=await get(origin+path);
  if(response.status()!==200)throw Error('RETAINED_PRIVATE_ROLLBACK_HTTP_FAILED');
  protectedHeaders(response.headers());
  const bytes=await response.body();
  if(createHash('sha256').update(bytes).digest('hex')!==rollback[key])throw Error('RETAINED_PRIVATE_ROLLBACK_BYTES_CHANGED');
  if(path.endsWith('.json')){const v=JSON.parse(bytes.toString('utf8'));if(v.revision!==rollback.source||v.classification!=='internal')throw Error('RETAINED_PRIVATE_ROLLBACK_SOURCE_CHANGED');}
 }
 return {...rollback,origin,private_headers:true,index_and_provenance_read_back:true,classification:'internal',provider_writes:0};
}

export async function validateNativeProtectedDocumentation(context,{origin,revision,expectedEnvironment,assets,origins,teamOrigin,anonymousGet,registry,icons,rollback,deadlineMs=720000}){
 origin=protectedDocsOrigin(origin+'/',expectedEnvironment);
 if(!/^[a-f0-9]{40}$/.test(revision)||typeof anonymousGet!=='function'||!Number.isSafeInteger(deadlineMs)||deadlineMs<1||deadlineMs>720000)throw Error('EXACT_PROTECTED_SOURCE_AND_BOUNDED_NATIVE_READS_REQUIRED');
 const before=[...context.pages()],page=await context.newPage(),auxiliary=new Map();let blocked=0,guard,timer;
 const controller=new AbortController();
 const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('OWNED_NATIVE_OBSERVATION_DEADLINE'));},deadlineMs);});
 try{return await Promise.race([deadline,(async()=>{
  guard=await guardOwnedHttp(context,page,origin,()=>blocked++);
  const response=await page.goto(origin+'/',{waitUntil:'domcontentloaded',timeout:30000});
  if(response?.status()!==200||new URL(page.url()).origin!==origin)throw Error('GENUINE_APPROVED_ENGINEERING_SESSION_REQUIRED');
  if(await page.evaluate(async()=>Boolean(navigator.serviceWorker?.controller)||Boolean((await navigator.serviceWorker?.getRegistrations())?.length)))throw Error('NATIVE_SERVICE_WORKER_UNVERIFIED');
  const get=value=>nativeGet(page,origin,value);
  const verified=await verifyProtectedAssets(get,origin,assets);
  const anonymous=await verifyAnonymousProtectedAssets(anonymousGet,origins,assets,teamOrigin);
  const owned=ownedAuditPage(page,context,auxiliary,()=>blocked++,guard.session,origin,controller.signal);
  await owned.setViewportSize({width:1440,height:900});
  const acceptance=await validateProtectedDocumentation({page:owned,get,origin,revision,environment:expectedEnvironment,registry,icons});
  if(expectedEnvironment==='staging'){
   const oldOrigin='https://docs.engineering.onesa.eu',oldPage=await context.newPage();let oldGuard;
   try{
    oldGuard=await guardOwnedHttp(context,oldPage,oldOrigin,()=>blocked++);
    const response=await oldPage.goto(oldOrigin+'/',{waitUntil:'domcontentloaded',timeout:30000});
    if(response?.status()!==200||new URL(oldPage.url()).origin!==oldOrigin)throw Error('GENUINE_RETAINED_ENGINEERING_SESSION_REQUIRED');
    acceptance.rollback_readiness=await verifyProtectedRollback(url=>nativeGet(oldPage,oldOrigin,url),rollback);
   }finally{await cleanupOwnedTargets(oldPage,oldGuard,new Map());}
  }else if(rollback!==undefined)throw Error('ROLLBACK_READINESS_BELONGS_TO_STAGING');
  if(blocked!==0||!before.every(tab=>context.pages().includes(tab)))throw Error('OWNER_CONTEXT_PRESERVATION');
  return {acceptance:{...acceptance,asset_security:verified.asset_security,anonymous_denials:anonymous},verified_protected_asset_responses:verified.verified,provider_writes:0,blocked_non_get_requests:0,original_tabs_preserved:true,session_values_read:false,validation_channel:'native-owner'};
 })()]);}finally{clearTimeout(timer);controller.abort();await cleanupOwnedTargets(page,guard,auxiliary);}
}
