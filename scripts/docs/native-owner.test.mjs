import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {gzipSync,brotliCompressSync} from 'node:zlib';
import {createRequire} from 'node:module';
import {nativeGet,exactPreviewOrigin,exactNativeDocsOrigin,validateNativePublicPreview,validateNativePublicPreflight,ownedAuditPage,emulateOwnedViewport,guardOwnedHttp,cleanupOwnedTargets} from './native-owner.mjs';
import {waitForInteractiveDocumentation,observeDocumentationFailure} from './acceptance.mjs';
const require=createRequire(new URL('../../onesa-ai-platform-frontend/apps/docs/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const PREVIEW='https://onesa-docs-synthetic-druhustles-projects.vercel.app';

test('hydration failure retains bounded state and phase without weakening the assertion',async t=>{
 const browser=await chromium.launch();t.after(()=>browser.close());
 const page=await browser.newPage();
 await page.setContent('<!doctype html><title>Private synthetic title</title><main>Not hydrated</main>');
 await assert.rejects(waitForInteractiveDocumentation(page,50,'mobile'),error=>{
  assert.equal(error.matcherResult?.name,'toHaveAttribute');
  assert.deepEqual(error.documentationObservation,{phase:'mobile',state:{readyState:'complete',hydrated:false,visible:true,scripts:0}});
  assert.ok(!JSON.stringify(error.documentationObservation).includes('Private synthetic title'));
  return true;
 });
 await page.locator('html').evaluate(node=>node.setAttribute('data-has-hydrated','true'));
 await waitForInteractiveDocumentation(page,50,'desktop');
});

test('failed hydration observation preserves the original failure and rejects arbitrary phase text',async t=>{
 const browser=await chromium.launch();t.after(()=>browser.close());
 const page=await browser.newPage();await page.setContent('<!doctype html><title>Synthetic</title>');
 const facade=new Proxy(page,{get(target,key){if(key==='evaluate')return async()=>{throw Error('Synthetic observation failure');};const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;}});
 await assert.rejects(waitForInteractiveDocumentation(facade,50,'https://private.invalid/?token=synthetic'),error=>{
  assert.equal(error.matcherResult?.name,'toHaveAttribute');
  assert.deepEqual(error.documentationObservation,{phase:'unspecified',state:null});
  return true;
 });
});

test('only exact public Preview origin is accepted',()=>{
 assert.equal(exactPreviewOrigin(PREVIEW+'/'),PREVIEW);
 for(const value of ['http://onesa-docs-synthetic-druhustles-projects.vercel.app/','https://other.vercel.app/','https://platform.onesa.eu/','https://onesa-engineering-docs.pages.dev/',PREVIEW+'/?token=value',PREVIEW+'/path','https://user@onesa-docs-synthetic-druhustles-projects.vercel.app/'])assert.throws(()=>exactPreviewOrigin(value));
});

test('production native observation accepts only the exact public canonical Docs origin',()=>{
 assert.equal(exactNativeDocsOrigin('https://docs.onesa.eu/','production'),'https://docs.onesa.eu');
 assert.equal(exactNativeDocsOrigin(PREVIEW+'/','staging'),PREVIEW);
 for(const value of [PREVIEW+'/','https://docs.engineering.onesa.eu/','https://docs.onesa.eu/?token=synthetic','https://docs.onesa.eu/path','https://user@docs.onesa.eu/','http://docs.onesa.eu/'])assert.throws(()=>exactNativeDocsOrigin(value,'production'));
 assert.throws(()=>exactNativeDocsOrigin('https://docs.onesa.eu/','staging'));
 assert.throws(()=>exactNativeDocsOrigin('https://docs.onesa.eu/','development'));
});

test('native reader refuses external URLs before any browser evaluation',async()=>{
 let calls=0;const page={url:()=>PREVIEW,evaluate:async()=>{calls++;}};
 for(const value of ['https://external.test/',PREVIEW+'/#fragment','https://user@onesa-docs-synthetic-druhustles-projects.vercel.app/'])await assert.rejects(nativeGet(page,PREVIEW,value));
 assert.equal(calls,0);
});

test('actual native GET redirects never reach a foreign server; compressed bytes remain intact',async t=>{
 let foreignRequests=0;const foreign=http.createServer((req,res)=>{foreignRequests++;res.end('foreign');});
 await new Promise(resolve=>foreign.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>foreign.close(resolve)));
 const foreignOrigin='http://127.0.0.1:'+foreign.address().port;
 const server=http.createServer((req,res)=>{
  if(req.url==='/redirect'){res.writeHead(302,{Location:foreignOrigin+'/'});res.end();}
  else if(req.url==='/json'||req.url==='/json.br'){res.setHeader('Content-Type','application/json');res.setHeader('Content-Encoding',req.url.endsWith('.br')?'br':'gzip');res.end((req.url.endsWith('.br')?brotliCompressSync:gzipSync)(Buffer.from('{"public":true}')));}
  else{res.setHeader('Content-Type','text/html');res.end('<!doctype html><title>Owned fixture</title><main>Public fixture</main>');}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch();t.after(()=>browser.close());const context=await browser.newContext();
 const original=await context.newPage();await original.goto(origin);const page=await context.newPage();await page.goto(origin);
 for(const suffix of ['/json','/json.br']){const result=await nativeGet(page,origin,origin+suffix);assert.equal(result.status(),200);assert.deepEqual(await result.json(),{public:true});}
 await assert.rejects(nativeGet(page,origin,origin+'/redirect'));assert.equal(foreignRequests,0);assert.ok(context.pages().includes(original));
});

test('native verification owns one page, blocks writes and closes only its page on missing session',async()=>{
 let closed=0,writes=0,listener;
 const original={},page={setExtraHTTPHeaders:async()=>{},goto:async()=>({status:()=>403}),url:()=>PREVIEW,isClosed:()=>false,close:async()=>closed++};
 const session={on:(name,handler)=>listener=handler,off:()=>{},detach:async()=>{},send:async name=>{if(name==='Fetch.enable')await listener({requestId:'synthetic',request:{method:'POST',url:PREVIEW+'/api'}});if(name==='Fetch.failRequest')writes++;}};
 const context={pages:()=>[original],newPage:async()=>page,newCDPSession:async()=>session};
 await assert.rejects(validateNativePublicPreview(context,{origin:PREVIEW,revision:'a'.repeat(40),verifyPublicAssets:async()=>({expected:1,verified:1})}),/GENUINE_OWNER_PREVIEW_SESSION_REQUIRED/);
 assert.equal(closed,1);assert.equal(writes,1);assert.deepEqual(context.pages(),[original]);
});

test('native validation requires a verifier function before creating a page',async()=>{
 let created=0;const context={newPage:async()=>created++};
 await assert.rejects(validateNativePublicPreview(context,{origin:PREVIEW,revision:'a'.repeat(40)}));assert.equal(created,0);
});

test('only a cancelled already-allowed GET avoids a false write-enforcement failure',async()=>{
 for(const [method,url,message,expected] of [
  ['GET',PREVIEW+'/asset.js','cdpSession.send: Protocol error (Fetch.continueRequest): Invalid InterceptionId.',0],
  ['GET',PREVIEW+'/asset.js','Protocol error (Fetch.continueRequest): Invalid InterceptionId.',0],
  ['GET',PREVIEW+'/asset.js','Synthetic transport failure',1],
  ['GET','https://foreign.invalid/','cdpSession.send: Protocol error (Fetch.continueRequest): Invalid InterceptionId.',2],
  ['POST',PREVIEW+'/api','cdpSession.send: Protocol error (Fetch.continueRequest): Invalid InterceptionId.',2],
 ]){
  let listener,violations=0;
  const page={setExtraHTTPHeaders:async()=>{},isClosed:()=>false};
  const session={on:(_name,fn)=>{listener=fn;},off:()=>{},detach:async()=>{},send:async command=>{if(command==='Fetch.continueRequest'||command==='Fetch.failRequest')throw Error(message);}};
  const guard=await guardOwnedHttp({newCDPSession:async()=>session},page,PREVIEW,()=>violations++);
  await listener({requestId:'synthetic',request:{method,url}});
  assert.equal(violations,expected);await guard.dispose();
 }
});

test('full preflight rejects production, missing byte verification and an unavailable owner session',async()=>{
 let created=0,closed=0;
 const original={},page={setExtraHTTPHeaders:async()=>{},goto:async()=>({status:()=>403}),url:()=>PREVIEW,isClosed:()=>false,close:async()=>closed++};
 const session={on:()=>{},off:()=>{},detach:async()=>{},send:async()=>{}};
 const context={pages:()=>[original],newPage:async()=>{created++;return page;},newCDPSession:async()=>session};
 const options={origin:PREVIEW,revision:'a'.repeat(40),expectedEnvironment:'staging',verifyPublicAssets:async()=>({verified:1,expected:1})};
 await assert.rejects(validateNativePublicPreflight(context,{...options,expectedEnvironment:'production'}),/NATIVE_STAGING_PREFLIGHT_REQUIRED/);
 await assert.rejects(validateNativePublicPreflight(context,{...options,verifyPublicAssets:undefined}),/SOURCE_AND_TRUSTED_PUBLIC_ASSETS_REQUIRED/);
 assert.equal(created,0);
 await assert.rejects(validateNativePublicPreflight(context,options),/GENUINE_OWNER_PREVIEW_SESSION_REQUIRED/);
 assert.equal(created,1);assert.equal(closed,1);assert.deepEqual(context.pages(),[original]);
});

test('a readable root is insufficient when preflight bytes or downstream UI checks fail',async()=>{
 for(const bytes of [{verified:0,expected:1},{verified:1,expected:1}]){
  let closed=0,verified=0;
  const original={},page={setExtraHTTPHeaders:async()=>{},goto:async()=>({status:()=>200}),url:()=>PREVIEW,evaluate:async()=>false,isClosed:()=>false,close:async()=>closed++};
  const session={on:()=>{},off:()=>{},detach:async()=>{},send:async()=>{}};
  const context={pages:()=>[original],newPage:async()=>page,newCDPSession:async()=>session};
  // The deliberately incomplete page cannot pass UI acceptance after valid bytes.
  await assert.rejects(validateNativePublicPreflight(context,{origin:PREVIEW,revision:'a'.repeat(40),expectedEnvironment:'staging',verifyPublicAssets:async()=>{verified++;return bytes;}}));
  assert.equal(verified,1);assert.equal(closed,1);assert.deepEqual(context.pages(),[original]);
 }
});

test('a stalled native observation closes its owned target and preserves the owner tab',async()=>{
 let closed=false;const original={};
 const page={setExtraHTTPHeaders:async()=>{},goto:async()=>new Promise(()=>{}),isClosed:()=>closed,close:async()=>{closed=true;}};
 const session={on:()=>{},off:()=>{},detach:async()=>{},send:async()=>{}};
 const context={pages:()=>[original],newPage:async()=>page,newCDPSession:async()=>session};
 await assert.rejects(validateNativePublicPreview(context,{origin:PREVIEW,revision:'a'.repeat(40),verifyPublicAssets:async()=>({verified:1,expected:1}),deadlineMs:30}),/OWNED_NATIVE_OBSERVATION_DEADLINE/);
 assert.equal(closed,true);assert.deepEqual(context.pages(),[original]);
});

test('an expired native audit cannot create further auxiliary targets',async()=>{
 const abort=new AbortController();abort.abort();let created=0;
 const facade=ownedAuditPage({}, {newPage:async()=>{created++;}},new Map(),()=>{},undefined,PREVIEW,abort.signal);
 await assert.rejects(facade.context().newPage(),/OWNED_NATIVE_OBSERVATION_DEADLINE/);
 assert.equal(created,0);
});


test('audit facade constrains auxiliary pages without altering the native shared context',async()=>{
 let blocked=0,aborted=0,listener;const originalMethod=async()=>{};
 const owned={isClosed:()=>false,setExtraHTTPHeaders:async()=>{}};
 const session={on:(name,handler)=>listener=handler,off:()=>{},detach:async()=>{},send:async name=>{if(name==='Fetch.enable')await listener({requestId:'synthetic',request:{method:'POST',url:PREVIEW+'/api'}});if(name==='Fetch.failRequest')aborted++;}};
 const context={newPage:async()=>owned,newCDPSession:async()=>session,addInitScript:originalMethod,route:originalMethod};
 const page={context:()=>context,marker(){return this===page;}},auxiliary=new Map();
 const facade=ownedAuditPage(page,context,auxiliary,()=>blocked++,undefined,PREVIEW);
 assert.equal(facade.marker(),true);assert.equal(await facade.context().newPage(),owned);assert.ok(auxiliary.has(owned));
 assert.equal(blocked,1);assert.equal(aborted,1);assert.equal(context.addInitScript,originalMethod);assert.equal(context.route,originalMethod);assert.equal(page.context(),context);
});

test('actual Axe aggregation uses owned constrained blank pages and preserves original tabs',async t=>{
 const {default:AxeBuilder}=require('@axe-core/playwright');
 const browser=await chromium.launch();t.after(()=>browser.close());const context=await browser.newContext();
 const original=await context.newPage(),page=await context.newPage(),auxiliary=new Map();let blocked=0;
 await page.setContent('<!doctype html><html lang="en"><title>Public fixture</title><main><h1>Public fixture</h1></main></html>');
 const results=await new AxeBuilder({page:ownedAuditPage(page,context,auxiliary,()=>blocked++,undefined,PREVIEW)}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
 assert.deepEqual(results.violations.filter(item=>['critical','serious'].includes(item.impact)),[]);
 assert.ok(auxiliary.size>0);assert.ok([...auxiliary.keys()].every(owned=>owned.isClosed()));for(const value of auxiliary.values())await value.dispose();assert.ok(context.pages().includes(original));assert.equal(context.pages().length,2);assert.equal(blocked,0);
});


test('viewport facade sends only bounded target emulation and never browser window changes',async()=>{
 const commands=[],session={send:async(...args)=>commands.push(args)};
 const page={setViewportSize:()=>{throw Error('SHARED_WINDOW_RESIZE_FORBIDDEN');}},facade=ownedAuditPage(page,{},new Set(),()=>{},session);
 await facade.setViewportSize({width:320,height:900});
 assert.deepEqual(commands,[['Emulation.setDeviceMetricsOverride',{width:320,height:900,screenWidth:320,screenHeight:900,deviceScaleFactor:1,mobile:false,dontSetVisibleSize:true}]]);
 for(const size of [{width:0,height:900},{width:5000,height:900},{width:true,height:900},{width:320,height:Infinity}])await assert.rejects(emulateOwnedViewport(session,size));
 assert.equal(commands.length,1);
});

test('actual target emulation preserves the original synthetic tab viewport and native window bounds',async t=>{
 const browser=await chromium.launch();t.after(()=>browser.close());const context=await browser.newContext({viewport:null});
 const original=await context.newPage(),page=await context.newPage();
 await original.setContent('<!doctype html><title>Original synthetic tab</title><main>Original</main>');
 await page.setContent('<!doctype html><title>Owned synthetic tab</title><main>Owned</main>');
 const originalSession=await context.newCDPSession(original),session=await context.newCDPSession(page);
 const beforeViewport=await original.evaluate(()=>({width:innerWidth,height:innerHeight}));
 const before=await originalSession.send('Browser.getWindowForTarget');
 await emulateOwnedViewport(session,{width:320,height:900});
 assert.equal(await page.evaluate(()=>innerWidth),320);
 const after=await originalSession.send('Browser.getWindowForTarget');
 assert.deepEqual(after,before);assert.deepEqual(await original.evaluate(()=>({width:innerWidth,height:innerHeight})),beforeViewport);
 assert.ok(context.pages().includes(original));await session.detach();await originalSession.detach();
});


test('owned target guard blocks every foreign redirect before a real foreign server receives GET',async t=>{
 let foreignRequests=0;const foreign=http.createServer((req,res)=>{foreignRequests++;res.end('foreign');});
 await new Promise(resolve=>foreign.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>foreign.close(resolve)));
 const server=http.createServer((req,res)=>{res.writeHead(302,{Location:'http://127.0.0.1:'+foreign.address().port+'/'});res.end();});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
 const browser=await chromium.launch();t.after(()=>browser.close());const context=await browser.newContext();
 const original=await context.newPage(),page=await context.newPage();let blocked=0;
 const guard=await guardOwnedHttp(context,page,'http://127.0.0.1:'+server.address().port,()=>blocked++);
 await assert.rejects(page.goto('http://127.0.0.1:'+server.address().port+'/'));
 assert.equal(foreignRequests,0);assert.equal(blocked,1);assert.ok(context.pages().includes(original));await guard.dispose();
});


test('a first auxiliary detach failure still closes every owned target and never closes original tabs',async()=>{
 const events=[],original={close:()=>{throw Error('ORIGINAL_TAB_CLOSE_FORBIDDEN');}};
 const owned=name=>({isClosed:()=>false,close:async()=>events.push('close:'+name)});
 const first=owned('first'),later=owned('later'),main=owned('main');
 const auxiliary=new Map([[first,{dispose:async()=>{events.push('dispose:first');throw Error('synthetic detach');}}],[later,{dispose:async()=>events.push('dispose:later')}] ]);
 await assert.rejects(cleanupOwnedTargets(main,{dispose:async()=>events.push('dispose:main')},auxiliary),/OWNED_TARGET_CLEANUP_FAILED/);
 for(const name of ['first','later','main'])assert.ok(events.includes('close:'+name));
 assert.ok(events.indexOf('close:first')<events.indexOf('dispose:first'));assert.ok(original);
});

test('main detach or late close failure is reported only after all remaining target cleanup',async()=>{
 const events=[],closed={isClosed:()=>true,close:async()=>{throw Error('closed page must not close again');}};
 const late={isClosed:()=>false,close:async()=>{events.push('late:close');throw Error('synthetic late failure');}};
 const main={isClosed:()=>false,close:async()=>events.push('main:close')};
 const auxiliary=new Map([[closed,{dispose:async()=>events.push('closed:dispose')}],[late,{dispose:async()=>events.push('late:dispose')}] ]);
 await assert.rejects(cleanupOwnedTargets(main,{dispose:async()=>{events.push('main:dispose');throw Error('synthetic main detach');}},auxiliary),/OWNED_TARGET_CLEANUP_FAILED/);
 assert.deepEqual(new Set(events),new Set(['closed:dispose','late:close','main:dispose','main:close']));
});

test('native byte verification excludes the preview toolbar and bypasses cached augmented HTML',async t=>{
 const original='<!doctype html><title>Source fixture</title><main>Source bytes</main>';
 const received=[];
 const server=http.createServer((req,res)=>{received.push({skip:req.headers['x-vercel-skip-toolbar'],cache:req.headers['cache-control']});
  res.setHeader('Content-Type','text/html');res.setHeader('Cache-Control','public,max-age=300');
  res.end(req.headers['x-vercel-skip-toolbar']==='1'?original:original+'<aside>Preview toolbar fixture</aside>');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
 const origin='http://127.0.0.1:'+server.address().port,browser=await chromium.launch();t.after(()=>browser.close());
 const context=await browser.newContext(),page=await context.newPage();await page.goto(origin+'/');
 assert.ok((await page.content()).includes('Preview toolbar fixture'));
 const response=await nativeGet(page,origin,origin+'/');assert.equal(await response.text(),original);
 assert.ok(received.some(x=>x.skip==='1'&&x.cache==='no-cache'));
});

test('toolbar and cache controls affect only the owned target and preserve original pages',async t=>{
 const received=[];const server=http.createServer((req,res)=>{received.push({path:req.url,skip:req.headers['x-vercel-skip-toolbar']});res.end('<!doctype html><title>Fixture</title>');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
 const origin='http://127.0.0.1:'+server.address().port,browser=await chromium.launch();t.after(()=>browser.close());
 const context=await browser.newContext(),original=await context.newPage(),page=await context.newPage();
 const guard=await guardOwnedHttp(context,page,origin,()=>assert.fail('Unexpected foreign or write request'));
 await page.goto(origin+'/owned');await original.goto(origin+'/original');
 assert.equal(received.find(x=>x.path==='/owned').skip,'1');assert.equal(received.find(x=>x.path==='/original').skip,undefined);
 await cleanupOwnedTargets(page,guard,new Map());assert.ok(context.pages().includes(original));
});


test('interaction failures retain only fixed renderer state and keep the original error',async t=>{
 const browser=await chromium.launch();t.after(()=>browser.close());const page=await browser.newPage();
 await page.setContent('<!doctype html><title>Private synthetic title</title><main>Fixture</main>');
 const error=new Error('Synthetic original interaction timeout');error.name='TimeoutError';
 await observeDocumentationFailure(error,page,'desktop');
 assert.equal(error.name,'TimeoutError');assert.equal(error.message,'Synthetic original interaction timeout');
 assert.deepEqual(error.documentationObservation,{phase:'desktop',state:{readyState:'complete',hydrated:false,visible:true,scripts:0}});
 assert.ok(!JSON.stringify(error.documentationObservation).includes('Private synthetic title'));
});

test('unavailable failure diagnostics cannot replace the original interaction failure',async()=>{
 const error=new Error('Original interaction failure');const original=error;
 await observeDocumentationFailure(error,{evaluate:async()=>{throw Error('Diagnostic unavailable');}},'untrusted-url');
 assert.equal(error,original);assert.equal(error.message,'Original interaction failure');
 assert.deepEqual(error.documentationObservation,{phase:'unspecified',state:null});
});

test('stalled failure diagnostics finish boundedly and do not turn failure into success',async()=>{
 const error=new Error('Original stalled interaction');const start=performance.now();
 await observeDocumentationFailure(error,{evaluate:()=>new Promise(()=>{})});
 assert.ok(performance.now()-start<3000);assert.equal(error.message,'Original stalled interaction');
 assert.deepEqual(error.documentationObservation,{phase:'unspecified',state:null});
});
