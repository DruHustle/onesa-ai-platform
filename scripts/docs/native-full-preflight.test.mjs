// Full native path against an isolated public static build; never owner sessions.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {validateNativePublicPreflight} from './native-owner.mjs';
const app=path.resolve('onesa-ai-platform-frontend/apps/docs');
const build=path.join(app,'build-public');
const require=createRequire(path.join(app,'package.json'));
const {chromium}=require('@playwright/test');
const origin='https://onesa-docs-fixture-druhustles-projects.vercel.app';
const mime={'.html':'text/html','.js':'application/javascript','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.pdf':'application/pdf','.css':'text/css','.xml':'application/xml','.txt':'text/plain','.mmd':'text/plain','.woff':'font/woff','.woff2':'font/woff2'};
const digest=body=>createHash('sha256').update(body).digest('hex');

async function fixture(t,{unhydrated=false,changedAsset=false}={}){
 const files=new Map();
 async function collect(directory){
  for(const item of await fs.readdir(directory,{withFileTypes:true})){
   const file=path.join(directory,item.name);
   if(item.isDirectory()){await collect(file);continue;}
   assert.ok(item.isFile());
   let route='/'+path.relative(build,file).split(path.sep).join('/');
   const extension=path.extname(file);
   if(route==='/index.html')route='/';
   else if(route.endsWith('/index.html'))route=route.slice(0,-11);
   else if(route.endsWith('.html'))route=route.slice(0,-5);
   const body=unhydrated&&extension==='.js'?Buffer.from('/* deliberately unhydrated fixture */'):await fs.readFile(file);
   assert.ok(!files.has(route));files.set(route,{body,mime:mime[extension]||'application/octet-stream'});
  }
 }
 await collect(build);
 const revision=JSON.parse(files.get('/generated/provenance.json').body).revision;
 const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'onesa-native-preflight-'));
 const keyFile=path.join(temporary,'fixture.key'),certificate=path.join(temporary,'fixture.crt');
 execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN='+new URL(origin).hostname,'-keyout',keyFile,'-out',certificate],{stdio:'ignore'});
 const server=https.createServer({key:await fs.readFile(keyFile),cert:await fs.readFile(certificate)},(request,response)=>{
  const url=new URL(request.url,origin);
  if(request.method!=='GET'){response.writeHead(405);response.end();return;}
  const key=decodeURIComponent(url.pathname).replace(/\/$/,'')||'/';
  const item=files.get(key);
  if(!item){response.writeHead(404,{'Content-Type':'text/plain'});response.end('Not found');return;}
  const body=changedAsset&&key==='/generated/search.json'?Buffer.from('[]'):item.body;
  response.writeHead(200,{'Content-Type':item.mime});response.end(body);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 // Transport-only proxy: exactly one synthetic HTTPS host reaches loopback.
 // This avoids replacing or disabling the native target's own CDP interception.
 const tunnels=new Set(),proxy=http.createServer((_request,response)=>{response.writeHead(403);response.end();});
 proxy.on('connect',(request,socket,head)=>{
  if(request.url!==new URL(origin).hostname+':443'){socket.end('HTTP/1.1 403 Forbidden\r\n\r\n');return;}
  const upstream=net.connect(server.address().port,'127.0.0.1',()=>{socket.write('HTTP/1.1 200 Connection Established\r\n\r\n');if(head.length)upstream.write(head);socket.pipe(upstream);upstream.pipe(socket);});
  tunnels.add(socket);tunnels.add(upstream);
  socket.on('error',()=>upstream.destroy());upstream.on('error',()=>socket.destroy());
  socket.on('close',()=>{tunnels.delete(socket);upstream.destroy();});upstream.on('close',()=>{tunnels.delete(upstream);socket.destroy();});
 });
 await new Promise(resolve=>proxy.listen(0,'127.0.0.1',resolve));
 let browser;
 t.after(async()=>{await browser?.close();for(const socket of tunnels)socket.destroy();server.closeAllConnections();await Promise.all([new Promise(resolve=>server.close(resolve)),new Promise(resolve=>proxy.close(resolve))]);await fs.rm(temporary,{recursive:true,force:true});});
 browser=await chromium.launch({proxy:{server:'http://127.0.0.1:'+proxy.address().port}});
 // Trust only this disposable fixture certificate inside this test context.
 const context=await browser.newContext({serviceWorkers:'block',ignoreHTTPSErrors:true});
 const violations=[],protocolFailures=[];const newSession=context.newCDPSession.bind(context);
 context.newCDPSession=async page=>{
  const session=await newSession(page);
  session.on('Fetch.requestPaused',({request})=>{
   const url=new URL(request.url);
   if(request.method!=='GET'||url.origin!==origin)violations.push({method:request.method,origin:url.origin,path:url.pathname});
  });
  const send=session.send.bind(session);
  session.send=async(command,...args)=>{
   try{return await send(command,...args);}
   catch(error){if(command.startsWith('Fetch.')){protocolFailures.push({command,message:String(error.message).slice(0,400)});if(protocolFailures.length===1)console.error(JSON.stringify({firstFixtureProtocolFailure:protocolFailures[0]}));}throw error;}
  };
  return session;
 };
 const original=await context.newPage();await original.setContent('<!doctype html><title>Preserved fixture tab</title>');
 let verified=0;
 async function observe(){
  try{return await validateNativePublicPreflight(context,{origin,revision,expectedEnvironment:'staging',verifyPublicAssets:async get=>{
   for(const [route,item] of files){
    const response=await get(origin+route);
    assert.equal(response.status(),200);
    assert.equal(digest(await response.body()),digest(item.body),'Actual fixture asset changed');
    verified++;
   }
   return {verified,expected:files.size};
  }});}catch(error){error.fixtureObservation={originalTabPreserved:context.pages().includes(original),violations,protocolFailures};throw error;}
 }
 return {observe,context,original,files,verified:()=>verified};
}

test('complete public bytes and the full native UI matrix are required before readiness',async t=>{
 const f=await fixture(t);
 assert.deepEqual(await f.observe(),{state:'NATIVE_OWNER_SESSION_READY_NOT_QUALIFICATION',providerWrites:0,sessionValuesRead:false});
 assert.equal(f.verified(),f.files.size);assert.ok(f.files.size>100);
 assert.deepEqual(f.context.pages(),[f.original]);
});

test('a changed asset cannot produce readiness despite a readable root and provenance',async t=>{
 const f=await fixture(t,{changedAsset:true});
 await assert.rejects(f.observe(),/Actual fixture asset changed/);
 assert.deepEqual(f.context.pages(),[f.original]);
});

test('complete readable bytes without working UI cannot produce readiness',async t=>{
 const f=await fixture(t,{unhydrated:true});
 await assert.rejects(f.observe(),error=>{
  assert.equal(error.matcherResult?.name,'toHaveAttribute');
  assert.equal(error.documentationObservation?.state?.hydrated,false);return true;
 });
 assert.equal(f.verified(),f.files.size);
 assert.deepEqual(f.context.pages(),[f.original]);
});
