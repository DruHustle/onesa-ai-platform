/** Explicit local performance experiment, outside mandatory correctness tests.
 * Browser-rAF-driven input; no gl.finish(), per-frame automation or FPS claim.
 * All created records belong to one disposable loopback-only synthetic account.
 */
import {chromium,webkit} from '../../onesa-ai-platform-frontend/apps/chat/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {randomUUID,createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const origin=process.env.ONESA_BROWSER_URL||'http://127.0.0.1:3218';
if(!['127.0.0.1','localhost','[::1]'].includes(new URL(origin).hostname))throw Error('Loopback fixture only');
const output=process.argv[2];if(!output)throw Error('Private output directory required');fs.mkdirSync(output,{recursive:true,mode:0o700});
const engine=process.argv[3]||'webkit',launcher={chromium,webkit}[engine];if(!launcher)throw Error('Unknown engine');
const browser=await launcher.launch(),context=await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000},deviceScaleFactor:1});
const requests=[],errors=[];await context.route('**/*',r=>{const u=new URL(r.request().url()),ok=!['http:','https:'].includes(u.protocol)||u.origin===origin;requests.push({origin:u.origin,path:u.pathname,allowed:ok});return ok?r.continue():r.abort();});
const page=await context.newPage();let phase='cold-chat';page.on('pageerror',e=>errors.push({phase,name:e.name,message:e.message}));page.setDefaultTimeout(30000);
const email=`twin-profile-${randomUUID()}@example.com`,password='twin-synthetic-profile-only-123!';
const source=execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim();
const dirty=execFileSync('git',['diff','--binary'],{encoding:'buffer',maxBuffer:32*1024*1024});
const model=fs.readFileSync('onesa-ai-platform-backend/app/twin_fixture_data/pump.glb');
const functionalFiles=execFileSync('git',['ls-files','--cached','--others','--exclude-standard','-z'],{encoding:'utf8'}).split('\0').filter(p=>p&&(p.startsWith('onesa-ai-platform-backend/app/')||p.startsWith('onesa-ai-platform-backend/migrations/')||p.startsWith('onesa-ai-platform-frontend/apps/chat/src/')||p.startsWith('scripts/twins/')));
const functionalFileHashes=Object.fromEntries(functionalFiles.map(p=>[p,createHash('sha256').update(fs.readFileSync(p)).digest('hex')]));
const summary={sourceCommit:source,functionalFileHashes,workingDiffSha256:createHash('sha256').update(dirty).digest('hex'),modelSha256:createHash('sha256').update(model).digest('hex'),hardware:{platform:os.platform(),machine:os.machine(),cpus:os.cpus()[0].model,memoryBytes:os.totalmem()},browser:engine,browserVersion:browser.version(),settings:{antialias:true,stencil:true,shadows:'PCFShadowMap',environmentCubePixels:64,network:'loopback',deviceScaleFactor:1},measurement:'Browser requestAnimationFrame drives scripted controls; warm-up 2 s, sustained 8 s. Render-completion callback intervals and CPU submission are not native FPS or GPU/present time. No gl.finish().',profiles:[]};
async function headers(){return {Origin:origin,'X-CSRF-Token':(await context.cookies(origin)).find(c=>c.name==='onesa_csrf')?.value||''};}
const view=page.getByTestId('equipment-model-loaded');
async function settled(){await page.waitForFunction(()=>document.querySelector('[data-testid="equipment-model-loaded"]')?.getAttribute('data-inspection-settled')==='true');}
async function button(name){await page.getByRole('button',{name,exact:true}).click();}
async function profile(name,control='orbit'){
 phase=name;await settled();await view.scrollIntoViewIfNeeded();
 const box=await page.locator('canvas').boundingBox();
 if(control==='orbit'){await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();}
 const value=await view.evaluate(async (el,{control})=>{
  const canvas=el.querySelector('canvas'),gl=canvas.getContext('webgl2'),ext=gl.getExtension('WEBGL_debug_renderer_info');
  const result={renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,canvas:[canvas.width,canvas.height],initial:{...el.dataset},intervals:[],cpuSubmitMs:[],drawCalls:[],renderedTriangles:[],geometryCounts:[],textureCounts:[],shaderPrograms:[],longTasks:[],longTaskObserverSupported:PerformanceObserver.supportedEntryTypes?.includes('longtask')||false,heapBefore:performance.memory?.usedJSHeapSize??null};
  const start=performance.now(),warm=2000,duration=8000;let last=null,lastControl=-1,seen=Number(el.dataset.renderCount||0),samples=0;
  const obs=new MutationObserver(()=>{const now=performance.now(),count=Number(el.dataset.renderCount||0);if(count===seen)return;seen=count;if(now-start<warm){last=null;return;}if(last!==null)result.intervals.push(now-last);last=now;
   result.cpuSubmitMs.push(Number(el.dataset.cpuSubmitMs));result.drawCalls.push(Number(el.dataset.drawCalls));result.renderedTriangles.push(Number(el.dataset.renderedTriangles));result.geometryCounts.push(Number(el.dataset.gpuGeometries));result.textureCounts.push(Number(el.dataset.gpuTextures));result.shaderPrograms.push(Number(el.dataset.shaderPrograms));samples++;});
  obs.observe(el,{attributes:true,attributeFilter:['data-render-count']});
  let long;try{long=new PerformanceObserver(list=>{for(const e of list.getEntries())if(e.startTime>=start+warm)result.longTasks.push(e.duration);});long.observe({entryTypes:['longtask']});}catch{}
  const rect=canvas.getBoundingClientRect(),setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  await new Promise(resolve=>{function tick(now){const t=now-start;if(t>=warm+duration){resolve();return;}
    if(control==='orbit')canvas.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,pointerId:1,pointerType:'mouse',buttons:1,clientX:rect.x+rect.width/2+50*Math.sin(t/1400),clientY:rect.y+rect.height/2+18*Math.sin(t/2100)}));
    else if(now-lastControl>=50){const label=control==='section'?'Section position':'Explosion percent';const input=document.querySelector(`input[aria-label="${label}"]`);const f=(Math.sin(t/1700)+1)/2;setter.call(input,String(control==='section'?Math.round(-60+f*120):Math.round(f*100)));input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));lastControl=now;}
    requestAnimationFrame(tick);
   }requestAnimationFrame(tick);});
  obs.disconnect();long?.disconnect();result.samples=samples;result.final={...el.dataset};result.heapAfter=performance.memory?.usedJSHeapSize??null;return result;
 },{control});
 if(control==='orbit')await page.mouse.up();
 const stats=values=>{const sorted=[...values].sort((a,b)=>a-b);return {n:sorted.length,median:sorted[Math.floor(sorted.length*.5)]??null,p95:sorted[Math.min(sorted.length-1,Math.ceil(sorted.length*.95)-1)]??null,min:sorted[0]??null,max:sorted.at(-1)??null};};
 summary.profiles.push({name,...value,statistics:{renderCompletionIntervalMs:stats(value.intervals),cpuSubmitMs:stats(value.cpuSubmitMs),drawCalls:stats(value.drawCalls),renderedTriangles:stats(value.renderedTriangles),geometryCounts:stats(value.geometryCounts),textureCounts:stats(value.textureCounts),shaderPrograms:stats(value.shaderPrograms)}});
 fs.writeFileSync(path.join(output,`profile-${engine}.json`),JSON.stringify(summary,null,2),{mode:0o600});
 await settled();await view.screenshot({path:path.join(output,`profile-${engine}-${page.viewportSize().width}-${name}.png`)});
}
try{
 const reg=await page.request.post('/api/v1/auth/register',{headers:{Origin:origin},data:{email,password,display_name:'Disposable performance fixture'}});if(reg.status()!==201)throw Error('Fixture registration');
 // Observe the actual startup responses before leaving Chat; optional 404 is
 // allowed, and an unread response cannot hold a global network-idle heuristic.
 const startup=['auth/me','models','conversations','knowledge/documents','twins/readiness','industrial/assets','documentation/access'].map(path=>page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/'+path).then(r=>{if(r.status()!==200&&!(path==='industrial/assets'&&r.status()===404))throw Error('Chat startup response: '+path);}));
 await page.goto('/');await page.getByRole('textbox',{name:'Message Onesa AI',exact:true}).waitFor();await Promise.all(startup);await page.waitForTimeout(500);summary.coldChat={canvasCount:await page.locator('canvas').count(),threeRegistered:await page.evaluate(()=>typeof window.__THREE__!=='undefined'),requests:requests.slice()};
 if(summary.coldChat.canvasCount||summary.coldChat.threeRegistered)throw Error('Ordinary Chat loaded engine');
 phase='cold-model';await page.goto('/industrial/twins');await button('Load isolated pump demonstration');await view.waitFor();await page.waitForFunction(()=>Number(document.querySelector('[data-testid="equipment-model-loaded"]')?.getAttribute('data-draw-calls'))>0);summary.coldLoad=await view.evaluate(el=>({...el.dataset}));
 await page.getByText('Section, subassembly and reveal controls',{exact:true}).click();
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  await page.setViewportSize(viewport);await page.getByRole('tab',{name:'Model',exact:true}).click();
  await button('Restore all');await button('Reset view');await profile('assembled-orbit');
  await profile('explosion-animation','explosion');await page.getByLabel('Explosion percent',{exact:true}).fill('100');await profile('exploded-orbit');
  await button('Restore all');await page.getByLabel('Section axis',{exact:true}).selectOption('z');await page.getByLabel('Reverse cut direction',{exact:true}).check();await page.getByLabel('Section plane',{exact:true}).check();await profile('section-movement','section');
  await page.getByLabel('Ghost housings',{exact:true}).check();await profile('ghost-orbit');
  await button('Restore all');await button('Copper winding phase A');await button('Isolate');await button('Focus selected');await profile('winding-closeup-orbit');
  await button('Restore all');await settled();await page.waitForTimeout(2000);const before=await view.getAttribute('data-render-count');await page.waitForTimeout(12000);const after=await view.getAttribute('data-render-count');summary.profiles.push({name:'idle-12s',viewport,before:Number(before),after:Number(after),renderDelta:Number(after)-Number(before)});
 }
 summary.errors=errors;summary.requests=requests;summary.nonOwnedRequests=requests.filter(r=>!r.allowed);if(errors.length||summary.nonOwnedRequests.length)throw Error('Browser or origin isolation failure');summary.status='OBSERVED';
}finally{
 const login=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email,password}});
 if(login.status()===200){const removed=await page.request.post('/api/v1/account/delete',{headers:await headers(),data:{current_password:password,confirmation:'DELETE MY ACCOUNT'}});summary.fixtureDeleted=removed.status()===204;}
 fs.writeFileSync(path.join(output,`profile-${engine}.json`),JSON.stringify(summary,null,2),{mode:0o600});await browser.close();
}
