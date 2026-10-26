// New owner-run probe. This private probe context is configuration, not authority.
process.on('uncaughtException',()=>{console.error('Oracle Twins probe refused; private context retained; no credentials logged');process.exitCode=1;});
// oracle_owner verifies the signed ledger before the pinned runner starts it.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {createRequire}=require('node:module');
const root=path.resolve(__dirname,'../..'),req=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/chat/package.json'));
const {chromium,expect}=req('@playwright/test');
function need(v,c){if(!v)throw Error(c);}
function privateJSON(p){const s=fs.lstatSync(p);need(s.isFile()&&!s.isSymbolicLink()&&(s.mode&0o077)===0&&s.uid===process.getuid()&&s.size<16384,'PRIVATE_PROBE_CONTEXT');return JSON.parse(fs.readFileSync(p));}
const ctx=privateJSON(process.env.ONESA_ORACLE_TWIN_CONTEXT),origin=new URL(ctx.origin).origin;
const local=['127.0.0.1','localhost','[::1]'].includes(new URL(origin).hostname);
need((ctx.environment==='staging'&&/^https:\/\/onesa-ai-platform-[a-z0-9-]+\.vercel\.app$/.test(origin))||(ctx.environment==='production'&&origin==='https://platform.onesa.eu')||(local&&ctx.environment==='development'&&process.argv.includes('--local-fixture')),'OWNED_PROBE_ORIGIN');
need(/^[a-f0-9]{40}$/.test(ctx.binding.candidate_commit)&&ctx.users.length===2&&ctx.users.every(u=>/^[a-f0-9-]{36}$/.test(u.id)&&/^release-audit-[0-9]+-[a-f0-9]{24}@example\.com$/.test(u.email)),'OWNED_FIXTURE_SCOPE');
const fixture=local&&ctx.fixture_directory?ctx.fixture_directory:'/private/reference';
const manifest=JSON.parse(fs.readFileSync(path.join(fixture,'manifest.json'))),binary=fs.readFileSync(path.join(fixture,'pump.glb'));
need(binary.length<=4*1024*1024&&crypto.createHash('sha256').update(binary).digest('hex')===manifest.artifact.sha256,'OWNED_MODEL_SOURCE_IDENTITY');
const report={binding:ctx.binding,operation_id:ctx.operation_id,environment:ctx.environment,workflow_run_id:0,checks:{},views:[],network:[],model_sha256:manifest.artifact.sha256,source_commit:ctx.binding.candidate_commit};
const output=ctx.output_dir,phase=process.argv.includes('--verify')?'verify':'prepare';
const savedFile=path.join(output,'twins-prepared.json');
async function main(){
 const browser=await chromium.launch({headless:true});let context;
 try{
  context=await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000},extraHTTPHeaders:ctx.bypass?{'x-vercel-protection-bypass':ctx.bypass}:{},...(phase==='verify'?{storageState:path.join(output,'twins-browser-state.json')}:{})});
  const errors=[];const page=await context.newPage();page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.name));
  await context.route('**/*',r=>{const u=new URL(r.request().url()),allowed=!['http:','https:'].includes(u.protocol)||u.origin===origin;report.network.push({origin:u.origin,path:u.pathname,allowed});return allowed?r.continue():r.abort();});
  async function headers(){return {Origin:origin,'X-CSRF-Token':(await context.cookies(origin)).find(c=>c.name==='onesa_csrf')?.value||''};}
  async function api(method,p,data,status=200){need(/^\/api\/v1\//.test(p)&&!p.includes('..'),'PROBE_API_PATH');report.last_api={method,path:p};const r=await page.request.fetch(p,{method,headers:await headers(),...(data===undefined?{}:{data})});need(r.status()===status,'PROBE_API_STATUS_'+method+'_'+r.status()+'_'+p.replaceAll('/','_'));return status===204?null:await r.json();}
  if(phase==='prepare'){const login=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email:ctx.users[0].email,password:ctx.users[0].password}});need(login.status()===200,'PROBE_SIGN_IN');}
  else {need((await page.request.get('/api/v1/auth/me')).status()===200,'SESSION_DID_NOT_SURVIVE_API_REPLACEMENT');report.checks.session_persistence='PASS';}
  if(!local){const cookies=await context.cookies(origin);need(cookies.find(c=>c.name==='onesa_session')?.secure===true,'SECURE_SESSION_COOKIE');}
  report.checks.authentication='PASS';
  let owned;
  if(phase==='prepare'){
   const ids=Object.fromEntries(manifest.components.map(c=>[c.id,crypto.randomUUID()]));
   const template=await api('POST','/api/v1/twins/templates',{name:'Owned synthetic qualification equipment',kind:'illustrative centrifugal pump',components:manifest.components.map(c=>({id:ids[c.id],name:c.label,parent_id:c.parentId?ids[c.parentId]:null,external_id:c.id,renderable:c.renderable,inventory:c.inventory,inventory_note:c.note||'',material:c.material||'',housing:c.housing||false}))},201);
   const upload=await page.request.post('/api/v1/twins/files',{headers:await headers(),multipart:{file:{name:'qualification-pump.glb',mimeType:'model/gltf-binary',buffer:binary}}});need(upload.status()===201,'AUTHENTICATED_MODEL_UPLOAD');const file=await upload.json();need(file.sha256===manifest.artifact.sha256,'HOSTED_FILE_DIGEST');
   const i=manifest.inspection;
   const model=await api('POST','/api/v1/twins/models',{file_id:file.id,template_id:template.id,mappings:manifest.mappings.map(m=>({node:m.sceneNode,component_id:ids[m.componentId]})),unit:'m',meters_per_unit:1,provenance:'Owned synthetic source-qualified reference; no equipment actuation.',inspection:{...i,motions:i.motions.map(m=>({...m,component_id:ids[m.component_id]})),closed_solids:i.closed_solids.map(id=>ids[id]),cover_components:i.cover_components.map(id=>ids[id]),housing_components:i.housing_components.map(id=>ids[id])}},201);
   const asset=await api('POST','/api/v1/twins/assets',{template_id:template.id,name:'Qualification pump',serial:'QUAL-'+ctx.operation_id},201);
   await api('PATCH',`/api/v1/twins/assets/${asset.id}`,{expected_revision:1,stage:'active',model_id:model.id});
   owned={asset_id:asset.id,file_id:file.id,model_id:model.id,component_mapping:ids,model_sha256:file.sha256};
   const manual=await page.request.post('/api/v1/twins/files',{headers:await headers(),multipart:{file:{name:'qualification-maintenance.txt',mimeType:'text/plain',buffer:fs.readFileSync(path.join(fixture,'maintenance.txt'))}}});need(manual.status()===201,'OWNED_MANUAL_UPLOAD');const manualFile=await manual.json();await api('POST',`/api/v1/twins/assets/${asset.id}/files/${manualFile.id}/index-document`,{});
   const detail=await api('GET',`/api/v1/twins/assets/${asset.id}`);const component=detail.asset.definition.components.find(c=>c.external_id==='bearing');need(component,'INSTALLED_COMPONENT_MAPPING');owned.selected_component_id=component.id;
   const source=await api('POST',`/api/v1/twins/assets/${asset.id}/sources`,{name:'Qualification simulated readings; no broker',mode:'simulated',bindings:[{tag:'vibration',component_id:component.id,metric:'vibration',unit:'mm/s',sample_seconds:1,stale_seconds:10,high:5,hysteresis:1}]},201);
   const ingest=await page.request.post(`/api/v1/twins/sources/${source.id}/readings`,{headers:{'X-Onesa-Source-Token':source.ingestion_token},data:{mode:'simulated',samples:[2,6,4.5,3].map((value,n)=>({message_id:crypto.randomUUID(),tag:'vibration',value,unit:'mm/s',observed_at:new Date(Date.now()-4000+n*1000).toISOString(),quality:'good'}))}});need([200,201,202].includes(ingest.status()),'BOUNDED_SIMULATED_INGESTION');
   fs.writeFileSync(savedFile,JSON.stringify(owned),{mode:0o600});
  }else owned=privateJSON(savedFile);
  const readiness=await api('GET','/api/v1/twins/readiness');need(readiness.enabled===true&&readiness.ready===true,'SCOPED_TWINS_READINESS');
  if(process.argv.includes('--api-only')){
   const detail=await api('GET',`/api/v1/twins/assets/${owned.asset_id}`);need(detail.asset.active_model_id===owned.model_id,'PERSISTED_MODEL_REVISION');
   const response=await page.request.get(`/api/v1/twins/files/${owned.file_id}/content`);need(response.status()===200&&crypto.createHash('sha256').update(await response.body()).digest('hex')===owned.model_sha256,'OWNED_BINARY_ROUNDTRIP');
   if(phase==='prepare'){
    const note=await api('POST',`/api/v1/twins/assets/${owned.asset_id}/notes`,{kind:'viewpoint',component_id:owned.selected_component_id,model_revision_id:owned.model_id,camera:[3,2,4,0,0,0],inspection_view:{explode:.65,section_enabled:true,section_axis:'y',ghost_housings:true}},201);owned.note_id=note.id;fs.writeFileSync(savedFile,JSON.stringify(owned),{mode:0o600});
   }
   const note=await api('GET',`/api/v1/twins/notes/${owned.note_id}`);need(note.payload.model_revision_id===owned.model_id&&note.component_id===owned.selected_component_id&&note.payload.inspection_view.explode===.65,'OWNED_SAVED_INSPECTION_BINDING');
   const evidence=await api('POST',`/api/v1/twins/assets/${owned.asset_id}/tools/evidence`,{mode:'simulated',start:new Date(Date.now()-3600000).toISOString(),end:new Date().toISOString(),component_id:owned.selected_component_id,question:'Inspect the qualified synthetic bearing vibration.',use_model:false});need(evidence.equipment?.id===owned.asset_id||evidence.evidence?.equipment?.id===owned.asset_id,'SCOPED_EQUIPMENT_EVIDENCE');
   const other=await browser.newContext({baseURL:origin,extraHTTPHeaders:ctx.bypass?{'x-vercel-protection-bypass':ctx.bypass}:{}});try{need((await other.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email:ctx.users[1].email,password:ctx.users[1].password}})).status()===200,'SECOND_SCOPED_IDENTITY');for(const p of [`/api/v1/twins/assets/${owned.asset_id}`,`/api/v1/twins/files/${owned.file_id}/content`,`/api/v1/twins/notes/${owned.note_id}`])need((await other.request.get(p)).status()===404,'FOREIGN_OWNER_DENIED');}finally{await other.close();}
   await context.storageState({path:path.join(output,'twins-browser-state.json')});fs.chmodSync(path.join(output,'twins-browser-state.json'),0o600);
   for(const key of ['owner_isolation','twins_model_delivery','twins_saved_state','twins_owner_context','database_persistence','file_persistence','optional_sources_absent'])report.checks[key]='PASS';report.checks.tls=local?'LOCAL_FIXTURE_ONLY':'PASS';report.scope='API protocol; renderer acceptance belongs to the frontend component';report.status='PASS';return;
  }
  await page.goto('/industrial/twins');await expect(page.getByRole('heading',{name:'Qualification pump',exact:true})).toBeVisible();
  const view=page.getByTestId('equipment-model-loaded');await view.waitFor();await expect.poll(async()=>Number(await view.getAttribute('data-draw-calls')),{timeout:60000}).toBeGreaterThan(0);
  need(Number(await view.getAttribute('data-triangles'))>90000,'ACTUAL_INTERIOR_MODEL_RENDER');
  const fileResponse=await page.request.get(`/api/v1/twins/files/${owned.file_id}/content`);need(fileResponse.status()===200&&crypto.createHash('sha256').update(await fileResponse.body()).digest('hex')===owned.model_sha256,'AUTHENTICATED_FILE_DELIVERY');report.checks.twins_model_delivery='PASS';
  const button=name=>page.getByRole('button',{name,exact:true}).click();
  if(phase==='prepare'){
   await page.getByText('Section, subassembly and reveal controls',{exact:true}).click();
   await page.getByLabel('Explosion percent',{exact:true}).fill('100');await expect(view).toHaveAttribute('data-explode-fraction','1.0000',{timeout:30000});
   await button('Restore all');await expect(view).toHaveAttribute('data-assembled-restoration-error','0');
   await page.getByLabel('Section axis',{exact:true}).selectOption('z');await page.getByLabel('Section plane',{exact:true}).check();await expect.poll(async()=>Number(await view.getAttribute('data-section-caps'))).toBeGreaterThan(0);
   await page.getByLabel('Reverse cut direction',{exact:true}).check();await page.getByLabel('Ghost housings',{exact:true}).check();
   await button('Bearing');await page.getByRole('tab',{name:'History',exact:true}).click();await button('Load history');await expect(page.getByRole('tabpanel',{name:'History'})).toContainText('threshold crossing');
   await page.getByRole('tab',{name:'Documents',exact:true}).click();await expect(page.getByRole('tabpanel',{name:'Documents'})).toContainText('qualification-maintenance');
   await button('Inspect selected evidence');await expect(page.getByLabel('Equipment evidence answer')).toContainText('deterministic evidence');
   await page.getByRole('tab',{name:'Model',exact:true}).click();await button('Restore all');await page.getByLabel('Explosion percent',{exact:true}).fill('65');await page.getByLabel('Section axis',{exact:true}).selectOption('y');await page.getByLabel('Section plane',{exact:true}).check();await page.getByLabel('Ghost housings',{exact:true}).check();await button('Save viewpoint');await expect(page.getByRole('button',{name:'Viewpoint 1',exact:true})).toBeVisible();
   report.checks.twins_inspection='PASS';
  }else{
   await button('Viewpoint 1');await expect(page.getByLabel('Explosion percent',{exact:true})).toHaveValue('65');await expect(page.getByLabel('Ghost housings',{exact:true})).toBeChecked();await expect(page.getByLabel('Section axis',{exact:true})).toHaveValue('y');report.checks.twins_saved_state='PASS';
   const detail=await api('GET',`/api/v1/twins/assets/${owned.asset_id}`);need(detail.asset.active_model_id===owned.model_id,'PERSISTED_MODEL_REVISION');report.checks.database_persistence='PASS';report.checks.file_persistence='PASS';
  }
  for(const theme of ['light','dark'])for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){await page.emulateMedia({colorScheme:theme});await page.setViewportSize(viewport);await view.scrollIntoViewIfNeeded();need(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'WORKSPACE_OVERFLOW');await page.screenshot({path:path.join(output,`twins-${phase}-${theme}-${viewport.width}.png`),fullPage:true});report.views.push({theme,viewport,actual_render:await view.getAttribute('data-draw-calls')});}
  await context.storageState({path:path.join(output,'twins-browser-state.json')});fs.chmodSync(path.join(output,'twins-browser-state.json'),0o600);
  await page.reload();await view.waitFor();await button('Viewpoint 1');await expect(page.getByLabel('Explosion percent',{exact:true})).toHaveValue('65');report.checks.twins_saved_state='PASS';
  const other=await browser.newContext({baseURL:origin,extraHTTPHeaders:ctx.bypass?{'x-vercel-protection-bypass':ctx.bypass}:{}});try{const login=await other.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email:ctx.users[1].email,password:ctx.users[1].password}});need(login.status()===200,'SECOND_SCOPED_IDENTITY');for(const p of [`/api/v1/twins/assets/${owned.asset_id}`,`/api/v1/twins/files/${owned.file_id}/content`])need((await other.request.get(p)).status()===404,'FOREIGN_OWNER_DENIED');}finally{await other.close();}
  report.checks.owner_isolation='PASS';report.checks.optional_sources_absent='PASS';need(errors.length===0&&report.network.every(r=>r.allowed),'BROWSER_OR_ASSET_ERRORS');report.checks.tls=local?'LOCAL_FIXTURE_ONLY':'PASS';
  await page.getByRole('link',{name:'Knowledge',exact:true}).click();await expect(page.getByRole('heading',{name:'Your knowledge',exact:true})).toBeVisible();await page.goto('/');need(await page.locator('canvas').count()===0,'ORDINARY_CHAT_ENGINE_ISOLATION');report.checks.chat_knowledge_retained='PASS';report.status='PASS';
 }catch(error){report.failure_category=/^[A-Za-z0-9_/-]{1,250}$/.test(error.message||'')?error.message:error.constructor.name;throw error;}finally{await context?.close();await browser.close();fs.writeFileSync(path.join(output,'twins-'+phase+'-ui.json'),JSON.stringify(report,null,2),{mode:0o600});}
}
main().then(()=>console.log(JSON.stringify({status:report.status,checks:report.checks}))).catch(()=>{console.error('Owned Twins hosted probe failed; inspect private receipt and captures; no credentials logged');process.exitCode=1;});
