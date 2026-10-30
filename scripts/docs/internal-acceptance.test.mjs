// Real renderer regression on a disposable local static fixture, never hosted evidence.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import os from 'node:os';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import {execFileSync} from 'node:child_process';
import {validateProtectedDocumentation} from './internal-acceptance.mjs';
import {validateNativeProtectedDocumentation} from './internal-native.mjs';
const require=createRequire(new URL('../../onesa-ai-platform-frontend/apps/docs/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const types={'.html':'text/html','.js':'application/javascript','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.pdf':'application/pdf','.css':'text/css','.ico':'image/x-icon','.mmd':'text/plain','.txt':'text/plain'};
const root=path.resolve(fileURLToPath(new URL('../..',import.meta.url)));

test('complete private UI is observed without changing existing disposable learning progress', {timeout:480000},async()=>{
 const build=path.resolve(process.env.ONESA_INTERNAL_DOCS_TEST_BUILD||path.join(root,'onesa-ai-platform-frontend/apps/docs/build-internal'));
 assert.equal((await fs.stat(path.join(build,'generated/provenance.json'))).isFile(),true,'Build the classified isolated fixture before this mandatory test');
 const provenance=JSON.parse(await fs.readFile(path.join(build,'generated/provenance.json'),'utf8'));
 const origin='https://onesa-engineering.test';
 async function read(value){
  const url=new URL(value);assert.equal(url.origin,origin);
  const selected=path.resolve(build,'.'+decodeURIComponent(url.pathname));assert.ok(selected===build||selected.startsWith(build+path.sep));
  for(const file of [selected,path.join(selected,'index.html'),selected+'.html'])try{if((await fs.stat(file)).isFile()){const body=await fs.readFile(file);return {status:()=>200,headers:()=>({'content-type':types[path.extname(file)]||'application/octet-stream'}),body:async()=>body,json:async()=>JSON.parse(body),text:async()=>body.toString()};}}catch(error){if(error.code!=='ENOENT'&&error.code!=='ENOTDIR')throw error;}
  return {status:()=>404,headers:()=>({}),body:async()=>Buffer.alloc(0)};
 }
 const browser=await chromium.launch(),context=await browser.newContext({serviceWorkers:'block'});
 try{
  await context.route('**/*',async route=>{const response=await read(route.request().url());await route.fulfill({status:response.status(),headers:response.headers(),body:await response.body()});});
  await context.addInitScript(()=>{if(localStorage.getItem('onesa-engineering-learning-v1')===null)localStorage.setItem('onesa-engineering-learning-v1','["1:0"]');});
  const page=await context.newPage();
  const registry=JSON.parse(await fs.readFile(path.join(root,'onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json'),'utf8'));
  const icons=JSON.parse(await fs.readFile(path.join(root,'onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json'),'utf8'));
  const environment=process.env.ONESA_INTERNAL_DOCS_TEST_ENVIRONMENT||'development';
  assert.ok(['development','staging'].includes(environment));
  const result=await validateProtectedDocumentation({page,get:read,origin,revision:provenance.revision,environment,registry,icons});
  assert.equal(result.result,'PASS');assert.equal(result.layouts.length,18);assert.equal(result.accessibility.length,18);assert.equal(result.architecture.length,18);assert.equal(result.chapters.length,17);assert.equal(result.api_reference.length,3);assert.equal(result.progress_mutations,0);assert.equal(result.existing_progress_preserved,true);assert.equal(result.manuals,22);
  assert.equal(await page.evaluate(()=>localStorage.getItem('onesa-engineering-learning-v1')),'["1:0"]');
 }finally{await browser.close();}
});

test('the full guarded private wrapper preserves existing tabs and progress while checking all bytes and rollback', {timeout:480000},async()=>{
 const build=path.resolve(process.env.ONESA_INTERNAL_DOCS_TEST_BUILD||path.join(root,'onesa-ai-platform-frontend/apps/docs/build-internal'));
 const origin='https://1234abcd.onesa-engineering-docs.pages.dev',canonical='https://docs.engineering.onesa.eu';
 const origins=[canonical,'https://onesa-engineering-docs.pages.dev',origin],teamOrigin='https://fixture.cloudflareaccess.com';
 const provenance=JSON.parse(await fs.readFile(path.join(build,'generated/provenance.json'),'utf8'));
 const privateHeaders={'cache-control':'private, no-store','x-robots-tag':'noindex, nofollow','x-content-type-options':'nosniff'};
 const assets=[];
 async function inventory(folder){for(const entry of await fs.readdir(folder,{withFileTypes:true})){
  const file=path.join(folder,entry.name);
  if(entry.isDirectory()){await inventory(file);continue;}
  assert.ok(entry.isFile());const relative=path.relative(build,file).split(path.sep).join('/');
  if(['_worker.js','_routes.json'].includes(relative))continue;
  const body=await fs.readFile(file);let route='/'+relative;
  if(route==='/index.html')route='/';else if(route.endsWith('/index.html'))route=route.slice(0,-10);else if(route.endsWith('.html'))route=route.slice(0,-5);
  assets.push({route,bytes:body.length,sha256:createHash('sha256').update(body).digest('hex'),mimes:[types[path.extname(file)]||'application/octet-stream']});
 }}
 await inventory(build);
 async function read(value){
  const url=new URL(value);assert.ok(origins.includes(url.origin));
  const selected=path.resolve(build,'.'+decodeURIComponent(url.pathname));assert.ok(selected===build||selected.startsWith(build+path.sep));
  for(const file of [selected,path.join(selected,'index.html'),selected+'.html'])try{if((await fs.stat(file)).isFile()){return {status:200,headers:{...privateHeaders,'content-type':types[path.extname(file)]||'application/octet-stream'},body:await fs.readFile(file)};}}catch(error){if(!['ENOENT','ENOTDIR'].includes(error.code))throw error;}
  return {status:404,headers:privateHeaders,body:Buffer.alloc(0)};
 }
 const hash=async name=>createHash('sha256').update(await fs.readFile(path.join(build,name))).digest('hex');
 const rollback={deployment_id:'1234abcd-1111-4111-8111-111111111111',source:provenance.revision,index_sha256:await hash('index.html'),provenance_sha256:await hash('generated/provenance.json')};
 const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'onesa-private-native-regression-'));
 const keyFile=path.join(temporary,'fixture.key'),certificate=path.join(temporary,'fixture.crt');
 execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN='+new URL(origin).hostname,'-keyout',keyFile,'-out',certificate],{stdio:'ignore'});
 let writes=0;
 const server=https.createServer({key:await fs.readFile(keyFile),cert:await fs.readFile(certificate)},async(request,response)=>{
  if(request.method!=='GET'){writes++;response.writeHead(405);response.end();return;}
  try{const actual=await read('https://'+request.headers.host+request.url);response.writeHead(actual.status,actual.headers);response.end(actual.body);}catch{response.writeHead(500);response.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 // Only these disposable HTTPS hosts reach loopback. Do not replace CDP interception.
 const hosts=new Set(origins.map(value=>new URL(value).hostname+':443')),tunnels=new Set();
 const proxy=http.createServer((_request,response)=>{response.writeHead(403);response.end();});
 proxy.on('connect',(request,socket,head)=>{
  if(!hosts.has(request.url)){socket.end('HTTP/1.1 403 Forbidden\r\n\r\n');return;}
  const upstream=net.connect(server.address().port,'127.0.0.1',()=>{socket.write('HTTP/1.1 200 Connection Established\r\n\r\n');if(head.length)upstream.write(head);socket.pipe(upstream);upstream.pipe(socket);});
  tunnels.add(socket);tunnels.add(upstream);socket.on('error',()=>upstream.destroy());upstream.on('error',()=>socket.destroy());
  socket.on('close',()=>{tunnels.delete(socket);upstream.destroy();});upstream.on('close',()=>{tunnels.delete(upstream);socket.destroy();});
 });
 await new Promise(resolve=>proxy.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({proxy:{server:'http://127.0.0.1:'+proxy.address().port}}),context=await browser.newContext({serviceWorkers:'block',ignoreHTTPSErrors:true,viewport:{width:1280,height:800}});
 try{
  await context.addInitScript(()=>{if(localStorage.getItem('onesa-engineering-learning-v1')===null)localStorage.setItem('onesa-engineering-learning-v1','["1:0"]');});
  const existing=await context.newPage();await existing.goto(origin+'/');const beforeViewport=existing.viewportSize();
  const registry=JSON.parse(await fs.readFile(path.join(root,'onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json'),'utf8'));
  const icons=JSON.parse(await fs.readFile(path.join(root,'onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json'),'utf8'));
  const result=await validateNativeProtectedDocumentation(context,{origin,revision:provenance.revision,expectedEnvironment:'staging',assets,origins,teamOrigin,registry,icons,rollback,anonymousGet:async(url,options)=>{
   assert.ok(origins.includes(new URL(url).origin));assert.deepEqual(options,{maxRedirects:0,maxRetries:0,timeout:15000});
   return {status:()=>302,headers:()=>({location:teamOrigin+'/cdn-cgi/access/login/fixture'})};
  }});
  assert.equal(result.acceptance.result,'PASS');assert.equal(result.verified_protected_asset_responses,assets.length);assert.equal(result.acceptance.anonymous_denials.length,assets.length*3);assert.equal(result.acceptance.rollback_readiness.index_and_provenance_read_back,true);
  assert.equal(result.blocked_non_get_requests,0);assert.equal(result.provider_writes,0);assert.equal(writes,0);assert.deepEqual(context.pages(),[existing]);assert.deepEqual(existing.viewportSize(),beforeViewport);
  assert.equal(await existing.evaluate(()=>localStorage.getItem('onesa-engineering-learning-v1')),'["1:0"]');
 }finally{await browser.close();for(const socket of tunnels)socket.destroy();server.closeAllConnections();await Promise.all([new Promise(resolve=>server.close(resolve)),new Promise(resolve=>proxy.close(resolve))]);await fs.rm(temporary,{recursive:true,force:true});}
});
