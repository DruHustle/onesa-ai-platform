// Read-only public Docs acceptance in a supplied native owner context; no session export.
import {validatePublicDocumentation} from './acceptance.mjs';

export function exactPreviewOrigin(value) {
 const url=new URL(value);
 if(url.protocol!=='https:'||url.port||url.username||url.password||url.search||url.hash||url.pathname!=='/'||!/^onesa-docs-[a-z0-9]+-druhustles-projects\.vercel\.app$/.test(url.hostname))throw Error('EXACT_PUBLIC_PREVIEW_ORIGIN');
 return url.origin;
}
export async function nativeGet(page,origin,value) {
 const url=new URL(value);
 if(url.origin!==origin||url.username||url.password||url.hash||new URL(page.url()).origin!==origin)throw Error('NATIVE_SAME_ORIGIN_GET');
 const result=await page.evaluate(async ({url,origin})=>{
  if(location.origin!==origin)throw Error('ORIGIN');
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
  try {
   // Vercel's documented automation header excludes its toolbar without an Access bypass.
   const response=await fetch(url,{method:'GET',credentials:'same-origin',cache:'no-store',redirect:'error',headers:{'x-vercel-skip-toolbar':'1','Cache-Control':'no-cache'},signal:controller.signal});
   if(new URL(response.url).origin!==origin)throw Error('REDIRECT');
   const reader=response.body?.getReader(),chunks=[];let size=0;
   if(reader)while(true){const chunk=await reader.read();if(chunk.done)break;size+=chunk.value.byteLength;if(size>16*1024*1024){await reader.cancel();throw Error('BODY_BOUND');}chunks.push(chunk.value);}
   const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
   let binary='';for(let start=0;start<bytes.length;start+=32768)binary+=String.fromCharCode(...bytes.subarray(start,start+32768));
   return {status:response.status,headers:{'content-type':response.headers.get('content-type')||''},body:btoa(binary)};
  }finally{clearTimeout(timer);}
 },{url:url.href,origin});
 const body=Buffer.from(result.body,'base64');
 return {status:()=>result.status,headers:()=>result.headers,body:async()=>body,text:async()=>body.toString('utf8'),json:async()=>JSON.parse(body.toString('utf8'))};
}
export async function guardOwnedHttp(context,page,origin,onViolation) {
 const session=await context.newCDPSession(page);
 const paused=async ({requestId,request})=>{
  let allowed=false;
  try{allowed=request.method==='GET'&&new URL(request.url).origin===origin;}catch{}
  if(!allowed)onViolation();
  try{await session.send(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId}:{requestId,errorReason:'BlockedByClient'});}catch(error){
   // Navigation can cancel an already-allowed same-origin GET before CDP resumes
   // it. This exact Chromium response cannot dispatch a forbidden request. Every
   // required response/byte/UI assertion remains mandatory; other errors fail.
   const cancelledRead=allowed&&/^(?:cdpSession\.send: )?Protocol error \(Fetch\.continueRequest\): Invalid InterceptionId\.$/.test(error.message);
   if(!cancelledRead&&!page.isClosed())onViolation();
  }
 };
 session.on('Fetch.requestPaused',paused);
 // These settings belong only to this disposable target, never the owner context.
 // https://vercel.com/docs/vercel-toolbar/managing-toolbar#disable-toolbar-for-automation
 try{await page.setExtraHTTPHeaders({'x-vercel-skip-toolbar':'1','Cache-Control':'no-cache'});await session.send('Network.setCacheDisabled',{cacheDisabled:true});await session.send('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});}catch{session.off('Fetch.requestPaused',paused);await session.detach();throw Error('OWNED_TARGET_INTERCEPTION_UNAVAILABLE');}
 return {session,dispose:async()=>{session.off('Fetch.requestPaused',paused);try{await session.detach();}catch{if(!page.isClosed())throw Error('OWNED_TARGET_SESSION_CLEANUP');}}};
}
export async function emulateOwnedViewport(session,size) {
 if(!session||!Number.isSafeInteger(size?.width)||!Number.isSafeInteger(size?.height)||size.width<120||size.height<120||size.width>4096||size.height>4096)throw Error('OWNED_TARGET_VIEWPORT_BOUND');
 // Target-only emulation: Playwright setViewportSize would resize the shared native window.
 await session.send('Emulation.setDeviceMetricsOverride',{width:size.width,height:size.height,screenWidth:size.width,screenHeight:size.height,deviceScaleFactor:1,mobile:false,dontSetVisibleSize:true});
}
export function ownedAuditPage(page,context,auxiliary,onWrite,session,origin,signal) {
 const facade={newPage:async()=>{
  if(signal?.aborted)throw Error('OWNED_NATIVE_OBSERVATION_DEADLINE');
  const owned=await context.newPage();
  if(signal?.aborted){await owned.close();throw Error('OWNED_NATIVE_OBSERVATION_DEADLINE');}
  try{const guard=await guardOwnedHttp(context,owned,origin,onWrite);auxiliary.set(owned,guard);return owned;}catch{await owned.close();throw Error('OWNED_AUDIT_TARGET_GUARD_UNAVAILABLE');}
 }};
 // A local facade for Axe's blank result page; never replace shared context methods.
 return new Proxy(page,{get(target,key){if(key==='setViewportSize')return size=>emulateOwnedViewport(session,size);if(key==='context')return()=>facade;const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;}});
}
export async function cleanupOwnedTargets(page,guard,auxiliary) {
 const targets=[...auxiliary.entries(),[page,guard]];
 const results=await Promise.allSettled(targets.map(async ([owned,ownedGuard])=>{
  let failure=false,closed=false;
  // Keep GET-only interception attached until the owned target is closed.
  try{if(!owned.isClosed())await owned.close();closed=true;}catch{failure=true;}
  if(closed)try{if(ownedGuard)await ownedGuard.dispose();}catch{failure=true;}
  if(failure)throw Error('OWNED_TARGET_CLEANUP_FAILED');
 }));
 if(results.some(result=>result.status==='rejected'))throw Error('OWNED_TARGET_CLEANUP_FAILED');
}
export function exactNativeDocsOrigin(value,environment){
 if(environment==='staging')return exactPreviewOrigin(value);
 const url=new URL(value);
 if(environment!=='production'||url.href!=='https://docs.onesa.eu/')throw Error('EXACT_CANONICAL_PUBLIC_DOCS_ORIGIN');
 return url.origin;
}
export async function validateNativePublicDocumentation(context,{origin,revision,verifyPublicAssets,expectedEnvironment,deadlineMs=720000}) {
 origin=exactNativeDocsOrigin(origin+'/',expectedEnvironment);
 if(!/^[a-f0-9]{40}$/.test(revision)||typeof verifyPublicAssets!=='function')throw Error('SOURCE_AND_TRUSTED_PUBLIC_ASSETS_REQUIRED');
 if(!Number.isSafeInteger(deadlineMs)||deadlineMs<1||deadlineMs>720000)throw Error('BOUNDED_NATIVE_OBSERVATION_DEADLINE_REQUIRED');
 const before=[...context.pages()],page=await context.newPage(),auxiliary=new Map();let blockedWrites=0,guard;
 const controller=new AbortController();let timer;
 const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('OWNED_NATIVE_OBSERVATION_DEADLINE'));},deadlineMs);});
 // Request interception belongs only to owned targets and applies to every redirect.
 try {
  return await Promise.race([deadline,(async()=>{
  guard=await guardOwnedHttp(context,page,origin,()=>blockedWrites++);
  const response=await page.goto(origin+'/',{waitUntil:'domcontentloaded',timeout:30000});
  if(response?.status()!==200||new URL(page.url()).origin!==origin)throw Error('GENUINE_OWNER_PREVIEW_SESSION_REQUIRED');
  if(await page.evaluate(async()=>Boolean(navigator.serviceWorker?.controller)||Boolean((await navigator.serviceWorker?.getRegistrations())?.length)))throw Error('NATIVE_SERVICE_WORKER_UNVERIFIED');
  const get=value=>nativeGet(page,origin,value);
  // Caller independently verifies every trusted public artifact byte before UI acceptance.
  const assets=await verifyPublicAssets(get);
  if(!Number.isSafeInteger(assets?.verified)||assets.verified<=0||assets.verified!==assets.expected)throw Error('TRUSTED_ALL_PUBLIC_BYTES_REQUIRED');
  const auditPage=ownedAuditPage(page,context,auxiliary,()=>blockedWrites++,guard.session,origin,controller.signal);
  await auditPage.setViewportSize({width:1440,height:900});
  const acceptance=await validatePublicDocumentation({page:auditPage,requestGet:get,origin,expectedRevision:revision,expectedEnvironment});
  if(blockedWrites!==0||!before.every(tab=>context.pages().includes(tab)))throw Error('OWNER_CONTEXT_PRESERVATION');
  return {acceptance,verified_public_asset_responses:assets.verified,provider_writes:0,blocked_non_get_requests:0,original_tabs_preserved:true,session_values_read:false,validation_channel:'native-owner'};
  })()]);
 }finally{clearTimeout(timer);controller.abort();await cleanupOwnedTargets(page,guard,auxiliary);}
}
export async function validateNativePublicPreview(context,options){
 return validateNativePublicDocumentation(context,{...options,expectedEnvironment:'staging'});
}

export async function validateNativePublicPreflight(context,options){
 // Exercise the same bytes and complete UI matrix before reserving qualification.
 // This result has no signature, qualification record or deployment authority.
 if(options.expectedEnvironment!=='staging')throw Error('NATIVE_STAGING_PREFLIGHT_REQUIRED');
 await validateNativePublicDocumentation(context,options);
 return {state:'NATIVE_OWNER_SESSION_READY_NOT_QUALIFICATION',providerWrites:0,sessionValuesRead:false};
}
