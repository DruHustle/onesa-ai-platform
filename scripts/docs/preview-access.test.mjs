import assert from 'node:assert/strict';
import test from 'node:test';
import {previewAccess,boundPreviewTransport} from './preview-access.mjs';
import http from 'node:http';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../../onesa-ai-platform-frontend/apps/docs/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const origin='https://onesa-docs-example.vercel.app',revision='a'.repeat(40),projectId='prj_Dtm2zO8sQQFqmnospPZgxbCi9Bbr';
const credential={projectId,secret:'synthetic-not-a-real-credential'},identity={url:origin,projectId,state:'READY',target:null,sourceRevision:revision,deploymentId:'dpl_Example'};
test('authenticated JSON transport is exact-origin and never follows redirects',async()=>{
 let calls=0;const access=previewAccess(credential,identity,origin,revision);
 await access.get({get:async(url,options)=>{calls++;assert.equal(url,origin+'/generated/provenance.json');assert.equal(options.maxRedirects,0);assert.equal(options.headers['x-vercel-protection-bypass'],credential.secret);return {status:()=>302};}},origin+'/generated/provenance.json');
 assert.equal(calls,1);await assert.rejects(access.get({get:()=>{calls++;}},'https://vercel.com/login'),/PUBLIC_DOCS_PREVIEW_REQUEST_ORIGIN/);assert.equal(calls,1);
});
test('browser assets use bounded redirects and external destinations receive no credential',async()=>{
 const access=previewAccess(credential,identity,origin,revision);let fetched=0,fulfilled=0,continued=0;
 const route={request:()=>({url:()=>origin+'/asset.js',method:()=> 'GET',headers:()=>({accept:'*/*'})}),fetch:async options=>{fetched++;assert.equal(options.maxRedirects,0);assert.equal(options.headers['x-vercel-protection-bypass'],credential.secret);return {};},fulfill:async()=>fulfilled++,continue:async()=>continued++};
 await access.route(route);assert.equal(fetched,1);assert.equal(fulfilled,1);assert.equal(continued,0);
 await access.route({...route,request:()=>({url:()=> 'https://onesa.eu/',method:()=> 'GET',headers:()=>({'x-vercel-protection-bypass':'inherited'})}),continue:async({headers})=>{continued++;assert.equal(Object.hasOwn(headers,'x-vercel-protection-bypass'),false);}});assert.equal(fetched,1);assert.equal(continued,1);
});
test('unknown project, production, source or deployment identity blocks before transport',()=>{
 for(const change of [{projectId:'wrong'},{target:'production'},{target:undefined},{state:'BUILDING'},{sourceRevision:'b'.repeat(40)},{url:'https://other.vercel.app'},{deploymentId:null}])assert.throws(()=>previewAccess(credential,{...identity,...change},origin,revision),/PUBLIC_DOCS_PREVIEW_ACCESS_SCOPE/);
 assert.throws(()=>previewAccess({...credential,projectId:'other'},identity,origin,revision),/PUBLIC_DOCS_PREVIEW_ACCESS_SCOPE/);
});
test('non-GET browser operations are blocked rather than authenticated',async()=>{
 let aborted=0;const access=previewAccess(credential,identity,origin,revision);
 await access.route({request:()=>({url:()=>origin+'/write',method:()=> 'POST',headers:()=>({})}),abort:async()=>aborted++,fetch:()=>assert.fail('transport must not run')});assert.equal(aborted,1);
});

test('actual cross-origin HTTP redirect never forwards the Preview credential',async()=>{
 const foreignHeaders=[],ownerHeaders=[];
 const foreign=http.createServer((req,res)=>{foreignHeaders.push(req.headers);res.writeHead(200,{'Content-Type':'text/html'});res.end('<main>Foreign destination</main>');});
 await new Promise(resolve=>foreign.listen(0,'127.0.0.1',resolve));
 const foreignOrigin=`http://127.0.0.1:${foreign.address().port}`;
 const owner=http.createServer((req,res)=>{ownerHeaders.push(req.headers);res.writeHead(302,{Location:foreignOrigin+'/destination'});res.end();});
 await new Promise(resolve=>owner.listen(0,'127.0.0.1',resolve));
 const ownerOrigin=`http://127.0.0.1:${owner.address().port}`,browser=await chromium.launch();
 try{
  const context=await browser.newContext(),access=boundPreviewTransport(credential.secret,ownerOrigin);
  await context.route('**/*',route=>access.route(route));
  const page=await context.newPage();await page.goto(ownerOrigin+'/redirect');assert.equal(new URL(page.url()).origin,foreignOrigin);
  assert.equal(ownerHeaders.length,1);assert.equal(ownerHeaders[0]['x-vercel-protection-bypass'],credential.secret);
  assert.equal(foreignHeaders.length,1);assert.equal(Object.hasOwn(foreignHeaders[0],'x-vercel-protection-bypass'),false);
  const response=await access.get(context.request,ownerOrigin+'/redirect');assert.equal(response.status(),302);assert.equal(foreignHeaders.length,1);
 }finally{await browser.close();await Promise.all([new Promise(resolve=>owner.close(resolve)),new Promise(resolve=>foreign.close(resolve))]);}
});

test('transport failures cannot expose provider request diagnostics or credential values',async()=>{
 const access=previewAccess(credential,identity,origin,revision);
 await assert.rejects(access.get({get:async()=>{throw new Error('raw transport includes '+credential.secret);}},origin+'/asset'),error=>error.message==='PUBLIC_DOCS_PREVIEW_TRANSPORT_FAILED'&&!String(error).includes(credential.secret));
 let aborted=0;await access.route({request:()=>({url:()=>origin+'/asset',method:()=> 'GET',headers:()=>({})}),fetch:async()=>{throw new Error(credential.secret);},abort:async()=>aborted++});assert.equal(aborted,1);
});
test('private credential and identity files must be bounded regular owner-only files',async()=>{
 const {installPreviewAccess}=await import('./preview-access.mjs'),fs=await import('node:fs/promises'),path=await import('node:path');
 const os=await import('node:os');
 const folder=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'onesa-preview-access-test-')));
 try{
  const file=path.join(folder,'access.json'),identityFile=path.join(folder,'identity.json');
  await fs.writeFile(file,JSON.stringify(credential),{mode:0o600});await fs.writeFile(identityFile,JSON.stringify(identity),{mode:0o600});
  let installed=0;const context={route:async()=>installed++},env={ONESA_DOCS_PREVIEW_ACCESS_FILE:file,ONESA_DOCS_PREVIEW_IDENTITY_FILE:identityFile};
  await installPreviewAccess(context,origin,revision,env);assert.equal(installed,1);
  await fs.chmod(identityFile,0o644);await assert.rejects(installPreviewAccess(context,origin,revision,env),/PUBLIC_DOCS_PREVIEW_PRIVATE_FILE/);assert.equal(installed,1);
  await fs.chmod(identityFile,0o600);await fs.chmod(folder,0o777);await assert.rejects(installPreviewAccess(context,origin,revision,env),/PUBLIC_DOCS_PREVIEW_PRIVATE_FILE/);await fs.chmod(folder,0o700);
  await fs.unlink(identityFile);await fs.symlink(file,identityFile);await assert.rejects(installPreviewAccess(context,origin,revision,env),/PUBLIC_DOCS_PREVIEW_PRIVATE_FILE/);
 }finally{await fs.rm(folder,{recursive:true,force:true});}
});
test('actual compressed HTML JS and JSON survive exact-origin fetch and fulfill',async()=>{
 const {gzipSync,brotliCompressSync}=await import('node:zlib'),headers=[];
 const bodies={
  '/':{mime:'text/html',body:'<!doctype html><main id="signal">Pending</main><script src="/asset.js"></script>'},
  '/asset.js':{mime:'application/javascript',body:'fetch("/value.json").then(response=>response.json()).then(value=>document.querySelector("#signal").textContent=value.message);'},
  '/value.json':{mime:'application/json',body:JSON.stringify({message:'Compressed assets rendered'})},
 };
 const server=http.createServer((req,res)=>{headers.push(req.headers);const brotli=req.url.startsWith('/br/'),entry=bodies[brotli?req.url.slice(3):req.url];if(!entry){res.writeHead(404);res.end();return;}res.writeHead(200,{'Content-Type':entry.mime,'Content-Encoding':brotli?'br':'gzip'});const body=brotli?entry.body.replaceAll('/asset.js','/br/asset.js').replaceAll('/value.json','/br/value.json'):entry.body;res.end((brotli?brotliCompressSync:gzipSync)(body));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const owner=`http://127.0.0.1:${server.address().port}`,browser=await chromium.launch();
 try{
  const context=await browser.newContext(),access=boundPreviewTransport(credential.secret,owner);await context.route('**/*',route=>access.route(route));const page=await context.newPage(),errors=[],types=[];page.on('pageerror',error=>errors.push(error.name));page.on('response',response=>types.push(response.headers()['content-type']));
  await page.goto(owner+'/');await page.locator('main').filter({hasText:'Compressed assets rendered'}).waitFor();assert.deepEqual(errors,[]);assert(types.includes('text/html'));assert(types.includes('application/javascript'));assert(types.includes('application/json'));await page.goto(owner+'/br/');await page.locator('main').filter({hasText:'Compressed assets rendered'}).waitFor();assert.deepEqual(errors,[]);assert.equal(headers.length,6);assert(headers.every(h=>h['x-vercel-protection-bypass']===credential.secret));
  const response=await access.get(context.request,owner+'/value.json');assert.deepEqual(await response.json(),{message:'Compressed assets rendered'});
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
});
