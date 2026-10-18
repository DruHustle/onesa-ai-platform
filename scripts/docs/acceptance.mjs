// Validate the emitted public static build without any backend or real user data.
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {installPreviewAccess} from './preview-access.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const docsRequire=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/docs/package.json'));
const {chromium,expect}=docsRequire('@playwright/test');
const chatRequire=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/chat/package.json'));
const {default:AxeBuilder}=chatRequire('@axe-core/playwright');
const build=path.join(root,'onesa-ai-platform-frontend/apps/docs/build-public');
const {version:documentationVersion}=JSON.parse(await fs.readFile(path.join(root,'onesa-ai-platform-frontend/apps/docs/package.json'),'utf8'));
const policy=JSON.parse(await fs.readFile(path.join(root,'docs/documentation-policy.json'),'utf8'));
const applications=JSON.parse(await fs.readFile(path.join(root,'onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json'),'utf8'));
function publicOrigin(value){
 let url;try{url=new URL(value);}catch{throw new Error('Application navigation requires a valid public origin.');}
 const host=url.hostname.toLowerCase().replace(/^\[|\]$/g,'').replace(/\.$/,'');
 const octets=/^\d+\.\d+\.\d+\.\d+$/.test(host)?host.split('.').map(Number):null;
 const privateAddress=octets&&(octets[0]===0||octets[0]===10||octets[0]===127||octets[0]===169&&octets[1]===254||octets[0]===172&&octets[1]>=16&&octets[1]<=31||octets[0]===192&&octets[1]===168||octets[0]===100&&octets[1]>=64&&octets[1]<=127);
 const privateIPv6=host.includes(':')&&(host==='::'||host==='::1'||/^f[cd]|^fe[89ab]|^::ffff:/.test(host));
 const privateHost=host==='localhost'||/\.(localhost|local|internal|lan|home)$/.test(host)||!host.includes('.')&&!host.includes(':')||privateIPv6;
 expect(url.protocol,'Application navigation requires HTTPS').toBe('https:');
 expect(Boolean(privateAddress||privateHost),'Application navigation must use public hosts').toBe(false);
 expect(Boolean(url.username||url.password),'Application navigation must not contain credentials').toBe(false);
 return url.origin;
}
const expectedApplications=applications.applications.map(application=>({
 label:application.label,
 href:publicOrigin(application.id==='ai'?(process.env.ONESA_APPLICATION_URL||application.href):application.id==='docs'?(process.env.ONESA_PUBLIC_DOCUMENTATION_URL||application.href):application.href),
}));
const types={'.html':'text/html','.js':'application/javascript','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.pdf':'application/pdf','.css':'text/css','.xml':'application/xml','.txt':'text/plain','.mmd':'text/plain'};
export async function waitForInteractiveDocumentation(page,timeout=10000,phase='unspecified'){
 // SSR markup is visible before React installs the dropdown's keyboard handler.
 // Docusaurus owns this public DOM marker; a missing hydration still fails boundedly.
 try{
  await expect(page.locator('html')).toHaveAttribute('data-has-hydrated','true',{timeout});
 }catch(error){
  // Retain only fixed diagnostic categories, never URLs, HTML, input or error text.
  // Keep the original assertion and deadline; this observation cannot turn FAIL into PASS.
  let state=null;
  let timer;
  try{state=await Promise.race([page.evaluate(()=>({
   readyState:document.readyState,
   hydrated:document.documentElement.getAttribute('data-has-hydrated')==='true',
   visible:document.visibilityState==='visible',
   scripts:document.scripts.length,
  })),new Promise(resolve=>{timer=setTimeout(()=>resolve(null),1500);})]);}catch{}
  finally{clearTimeout(timer);}
  error.documentationObservation={phase:['desktop','mobile'].includes(phase)?phase:'unspecified',state};
  throw error;
 }
}
export async function validatePublicDocumentation({page,requestGet,origin,expectedRevision,expectedEnvironment,storageFixture=false}){
const errors=[];const onError=e=>errors.push(e.name);page.on('pageerror',onError);
const evidence={origin,version:documentationVersion,diagrams:0,pdfs:0,links:0,navigation:[],icons:[],accessibility:[],widths:[]};
const provenanceResponse=await requestGet(origin+'/generated/provenance.json');
expect(provenanceResponse.status()).toBe(200);
expect(provenanceResponse.headers()['content-type'],'Public Docs provenance must be JSON, not a provider sign-in page').toContain('application/json');
const provenance=await provenanceResponse.json();
expect(provenance.classification).toBe('public');
if(expectedRevision)expect(provenance.revision).toBe(expectedRevision);
evidence.provenance={revision:provenance.revision,classification:provenance.classification};
async function checkIdentityIcons(){
 const source=JSON.parse(await fs.readFile(path.join(root,'onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json'),'utf8'));
 await expect(page.locator('link[rel="icon"]'),'Declare the browser favicon once').toHaveCount(1);
 await expect(page.locator('link[rel="icon"][type="image/svg+xml"]')).toHaveAttribute('href','/brand/icons/v1/onesa-docs.svg');
 await expect(page.locator('link[rel="icon"][type="image/svg+xml"]')).toHaveAttribute('sizes','any');
 await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute('sizes','180x180');
 for(const name of ['onesa-docs.svg','onesa-docs.ico','onesa-docs-180.png']){
  const asset=source.products[0].files.find(file=>file.name===name);
  const route=name.endsWith('.ico')?'/favicon.ico':'/brand/icons/v1/'+name;
  const response=await requestGet(origin+route);expect(response.status()).toBe(200);
  const mime=response.headers()['content-type'].split(';')[0];
  expect(name.endsWith('.ico')?['image/x-icon','image/vnd.microsoft.icon']:[asset.mime]).toContain(mime);
  expect(createHash('sha256').update(await response.body()).digest('hex')).toBe(asset.sha256);
  evidence.icons.push({path:route,status:200,mime,sha256:asset.sha256});
 }
}
async function checkApplicationsNavigation(view){
 await waitForInteractiveDocumentation(page,10000,view);
 let dropdown;
 if(view==='mobile'){
  await page.getByRole('button',{name:'Toggle navigation bar',exact:true}).click();
  const sidebar=page.locator('.navbar-sidebar');await expect(sidebar).toBeVisible();
  dropdown=sidebar.locator('.menu__list-item').filter({has:page.getByRole('button',{name:'Onesa applications',exact:true})});
  await dropdown.getByRole('button',{name:'Onesa applications',exact:true}).click();
  await expect(dropdown.getByRole('button',{name:'Collapse the dropdown',exact:true})).toHaveAttribute('aria-expanded','true');
 }else{
  dropdown=page.locator('.navbar__items .dropdown').filter({has:page.getByRole('button',{name:'Onesa applications',exact:true})});
  await dropdown.getByRole('button',{name:'Onesa applications',exact:true}).press('Enter');
  await expect(dropdown.getByRole('button',{name:'Onesa applications',exact:true})).toHaveAttribute('aria-expanded','true');
 }
 const menu=dropdown.locator(view==='mobile'?':scope > .menu__list':'.dropdown__menu');
 await expect(menu).toBeVisible();const links=menu.locator('a[href]');
 await expect(links).toHaveCount(expectedApplications.length);
 const emitted=await links.evaluateAll(nodes=>nodes.map(link=>({label:link.textContent.trim(),href:link.getAttribute('href'),target:link.target,rel:link.rel})));
 const actual=emitted.map(link=>{
  const href=publicOrigin(link.href);const url=new URL(link.href);
  expect(url.pathname,'Applications link to their public origin, not a private route').toBe('/');
  expect(url.search+url.hash,'Application links must not contain query parameters or fragments').toBe('');
  if(link.target==='_blank')expect(link.rel.split(/\s+/),'External links need noopener').toContain('noopener');
  return {label:link.label,href};
 });
 expect(actual,`${view} applications dropdown must match the pinned product registry`).toEqual(expectedApplications);
 for(let index=0;index<expectedApplications.length;index++){
  await expect(links.nth(index)).toBeVisible();
  expect(await links.nth(index).locator('svg').count(),'Application links have no decorative external-link icons').toBe(0);
 }
 evidence.navigation.push({view,links:actual});
 if(view==='mobile')await page.getByRole('button',{name:'Close navigation bar',exact:true}).click();
 else await dropdown.getByRole('button',{name:'Onesa applications',exact:true}).press('Enter');
}
try{
 await page.emulateMedia({colorScheme:'light'});await page.goto(origin+'/');await expect(page.locator('.appearance-control')).toHaveCount(0);await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 await checkIdentityIcons();
 await checkApplicationsNavigation('desktop');
 await page.setViewportSize({width:390,height:900});await page.goto(origin+'/');await checkApplicationsNavigation('mobile');await page.setViewportSize({width:1440,height:900});
 const catalog=await (await requestGet(origin+'/generated/diagrams.json')).json();
 expect(catalog.map(d=>d.id).sort()).toEqual([...policy.public_diagrams].sort());
 for(const diagram of catalog)for(const ext of ['svg','png','mmd','pdf']){
  const response=await requestGet(`${origin}/generated/diagrams/${diagram.id}.${ext}`);expect(response.status()).toBe(200);expect((await response.body()).length).toBeGreaterThan(20);
 }
 const manifest=await (await requestGet(origin+'/generated/manuals.json')).json();
 expect(manifest.map(m=>m.category).sort()).toEqual([...policy.public_pdfs].sort());
 for(const manual of manifest){const response=await requestGet(origin+'/generated/manuals/'+encodeURIComponent(manual.file));expect(response.status()).toBe(200);expect(response.headers()['content-type']).toContain('application/pdf');expect((await response.body()).subarray(0,5).toString()).toBe('%PDF-');expect(manual.classification).toBe('public');expect(manual.version).toBe(documentationVersion);expect(manual.pages).toBeGreaterThanOrEqual(3);evidence.pdfs++;}
 for(const url of ['/docs/architecture/ONESA_DESIGN_SYSTEM','/docs/operations/TAILSCALE_ADMINISTRATION','/generated/diagrams/onesa-design-system.svg','/generated/diagrams/tailscale-administration.pdf','/onboarding','/generated/engineering-navigation.json','/docs/onboarding/START_HERE','/generated/diagrams/ecosystem-current.svg','/database','/generated/database.json','/docs/ecosystem/PORTAL_DATABASE','/docs/security/SECURITY_ARCHITECTURE','/generated/diagrams/portal-database.svg','/generated/diagrams/robot-database.png','/generated/manuals/private.pdf'])expect((await requestGet(origin+url)).status()).toBe(404);
 const portal=await (await requestGet(origin+'/generated/openapi-portal.json')).json();expect(Object.keys(portal.paths).every(p=>p.startsWith('/api/v1/public/'))).toBe(true);
 const robots=await (await requestGet(origin+'/robots.txt')).text();expect(robots).toContain('Allow: /');expect(robots).toContain('Sitemap: https://docs.onesa.eu/sitemap.xml');
 const sitemap=await (await requestGet(origin+'/sitemap.xml')).text();expect(sitemap).toContain('https://docs.onesa.eu/');expect(sitemap).not.toContain('localhost');expect(sitemap).not.toContain('/docs/ecosystem/');
 const publicRoutes=[...new Set([...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match=>new URL(match[1]).pathname))];
 expect(publicRoutes.length).toBeGreaterThan(10);
 for(const mode of ['light','dark']){
  await page.emulateMedia({colorScheme:mode});
 for(const width of [320,1440]) for(const route of publicRoutes){
  await page.setViewportSize({width,height:900});
  await page.goto(origin+route);await expect(page.locator('main').first()).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme',mode);await page.waitForLoadState('networkidle');
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  evidence.accessibility.push({route,mode,width,violations:results.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))});
  const blocking=results.violations.filter(v=>['critical','serious'].includes(v.impact));
  expect(blocking.map(v=>({id:v.id,targets:v.nodes.slice(0,4).map(n=>({target:n.target,summary:n.failureSummary}))})),`Accessibility at ${route}`).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${mode} ${route} overflow at ${width}px`).toBe(true);
  const links=await page.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')).filter(h=>h?.startsWith('/')&&!h.startsWith('//')));
  for(const url of new Set(links)){expect((await requestGet(origin+url.split('#')[0])).status(),`Broken public link: ${url}`).toBe(200);evidence.links++;}
 }
 }
 const mode='dark';
 await page.goto(origin+'/architecture');
 for(const view of [...new Set(catalog.map(d=>d.view))]){
  await page.getByRole('button',{name:view==='logical'?'Logical architecture':'Deployment architecture',exact:true}).click();
  for(const diagram of catalog.filter(d=>d.view===view)){
   await page.getByLabel('Diagram',{exact:true}).selectOption(diagram.id);await expect(page.locator('.diagram-canvas svg')).toBeVisible();
   await expect(page.locator('.diagram-panel')).toContainText(diagram.title);await page.getByLabel('Select a component').selectOption({index:1});await expect(page.locator('.component-detail')).toBeVisible();evidence.diagrams++;
  }
 }
 await page.getByLabel('Zoom in',{exact:true}).click();await expect(page.locator('.diagram-canvas > div')).toHaveAttribute('style',/1.25/);
 await page.locator('.diagram-canvas').focus();await page.keyboard.press('ArrowRight');await expect(page.locator('.diagram-canvas > div')).toHaveAttribute('style',/30px/);
 await page.getByRole('button',{name:'Reset',exact:true}).click();await page.getByRole('button',{name:'Enlarge diagram',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByLabel('Zoom in',{exact:true})).toBeFocused();await page.keyboard.press('Shift+Tab');await expect(page.getByRole('link',{name:'Editable Mermaid'})).toBeFocused();await page.keyboard.press('Tab');await expect(page.getByLabel('Zoom in',{exact:true})).toBeFocused();await page.keyboard.press('Escape');await expect(page.locator('.diagram-panel.expanded')).toHaveCount(0);await expect(page.getByRole('button',{name:'Enlarge diagram',exact:true})).toBeFocused();
 await page.goto(origin+'/api-explorer');for(const product of ['ai','portal','robot']){await page.getByLabel('API product').selectOption(product);await expect(page.locator('.swagger-ui .opblock').first()).toBeVisible();await expect(page.getByRole('button',{name:'Try it out',exact:true})).toHaveCount(0);}
 await page.goto(origin+'/');await page.keyboard.press('Control+k');await page.getByLabel('Search documentation').fill('Robot');await expect(page.locator('.search-results a').first()).toBeVisible();await page.keyboard.press('Escape');
 for(const width of [320,390,768,1024,1440])for(const route of ['/','/architecture','/downloads','/api-explorer']){
  await page.setViewportSize({width,height:900});await page.goto(origin+route);await expect(page.locator('main').first()).toBeVisible();
  if(route==='/api-explorer')await expect(page.locator('.swagger-ui .opblock').first()).toBeVisible();
  if(route==='/architecture')await expect(page.locator('.diagram-canvas svg')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${route} overflow at ${width}px`).toBe(true);evidence.widths.push({mode,width,route,overflow:false});
 }
 await page.emulateMedia({colorScheme:'light'});await page.goto(origin+'/');await page.getByLabel('Search documentation').fill('Robot');await page.getByLabel('Search documentation').focus();await page.emulateMedia({colorScheme:'dark'});await expect(page.getByLabel('Search documentation')).toHaveValue('Robot');await expect(page.getByLabel('Search documentation')).toBeFocused();if(storageFixture){expect(await page.evaluate(()=>localStorage.getItem('theme'))).toBeNull();expect(await page.evaluate(()=>localStorage.getItem('onesa-unrelated-fixture'))).toBe('preserved');}
 if(expectedEnvironment){
  expect(['development','staging','production']).toContain(expectedEnvironment);
  await expect(page.locator('.docs-audience')).toHaveText((expectedEnvironment==='production'?'':expectedEnvironment.toUpperCase()+' · ')+'Public developer documentation');
  evidence.environment_context=expectedEnvironment;
 }
 expect(errors).toEqual([]);return {result:'PASS',...evidence};
}finally{page.off('pageerror',onError);}
}

async function main(){
const server=http.createServer(async(req,res)=>{
 try{
  const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  const requested=path.resolve(build,'.'+pathname);
  if(!requested.startsWith(build+path.sep)&&requested!==build){res.writeHead(404);res.end();return;}
  for(const file of [requested,path.join(requested,'index.html'),requested+'.html']){
   try{const stat=await fs.stat(file);if(stat.isFile()){res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream'});res.end(await fs.readFile(file));return;}}catch{}
  }
  res.writeHead(404);res.end('Not found');
 }catch{res.writeHead(400);res.end('Invalid request');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=process.env.ONESA_DOCS_TEST_URL||`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch();
const context=await browser.newContext({serviceWorkers:'block'});
const previewAccess=await installPreviewAccess(context,origin,process.env.GITHUB_SHA);
const requestGet=url=>previewAccess.get(context.request,url);
await context.addInitScript(()=>{Date.prototype.getHours=()=>12;});
await context.addInitScript(()=>{localStorage.setItem('theme','dark');localStorage.setItem('onesa-unrelated-fixture','preserved');});
const page=await context.newPage();
try{console.log(JSON.stringify(await validatePublicDocumentation({page,requestGet,origin,expectedRevision:process.env.GITHUB_SHA,expectedEnvironment:process.env.ONESA_DOCS_EXPECTED_ENVIRONMENT,storageFixture:true}),null,2));}
finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await main();
