// Validate the emitted public static build without any backend or real user data.
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const docsRequire=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/docs/package.json'));
const {chromium,expect}=docsRequire('@playwright/test');
const chatRequire=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/chat/package.json'));
const {default:AxeBuilder}=chatRequire('@axe-core/playwright');
const build=path.join(root,'onesa-ai-platform-frontend/apps/docs/build-public');
const policy=JSON.parse(await fs.readFile(path.join(root,'docs/documentation-policy.json'),'utf8'));
const types={'.html':'text/html','.js':'application/javascript','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.pdf':'application/pdf','.css':'text/css','.xml':'application/xml','.txt':'text/plain','.mmd':'text/plain'};
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
const context=await browser.newContext();
await context.addInitScript(()=>{Date.prototype.getHours=()=>Number(sessionStorage.getItem('onesa-test-hour')||12);});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const evidence={origin,version:policy.version,diagrams:0,pdfs:0,links:0,accessibility:[],widths:[]};
try{
 await page.goto(origin+'/');await expect(page.locator('.appearance-control')).toHaveCount(0);await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 const catalog=await (await context.request.get(origin+'/generated/diagrams.json')).json();
 expect(catalog.map(d=>d.id).sort()).toEqual([...policy.public_diagrams].sort());
 for(const diagram of catalog)for(const ext of ['svg','png','mmd','pdf']){
  const response=await context.request.get(`${origin}/generated/diagrams/${diagram.id}.${ext}`);expect(response.status()).toBe(200);expect((await response.body()).length).toBeGreaterThan(20);
 }
 const manifest=await (await context.request.get(origin+'/generated/manuals.json')).json();
 expect(manifest.map(m=>m.category).sort()).toEqual([...policy.public_pdfs].sort());
 for(const manual of manifest){const response=await context.request.get(origin+'/generated/manuals/'+encodeURIComponent(manual.file));expect(response.status()).toBe(200);expect(response.headers()['content-type']).toContain('application/pdf');expect((await response.body()).subarray(0,5).toString()).toBe('%PDF-');expect(manual.classification).toBe('public');expect(manual.version).toBe(policy.version);expect(manual.pages).toBeGreaterThanOrEqual(3);evidence.pdfs++;}
 for(const url of ['/onboarding','/generated/engineering-navigation.json','/docs/onboarding/START_HERE','/generated/diagrams/ecosystem-current.svg','/database','/generated/database.json','/docs/ecosystem/PORTAL_DATABASE','/docs/security/SECURITY_ARCHITECTURE','/generated/diagrams/portal-database.svg','/generated/diagrams/robot-database.png','/generated/manuals/private.pdf'])expect((await context.request.get(origin+url)).status()).toBe(404);
 const portal=await (await context.request.get(origin+'/generated/openapi-portal.json')).json();expect(Object.keys(portal.paths).every(p=>p.startsWith('/api/v1/public/'))).toBe(true);
 const robots=await (await context.request.get(origin+'/robots.txt')).text();expect(robots).toContain('Allow: /');expect(robots).toContain('Sitemap: https://docs.onesa.eu/sitemap.xml');
 const sitemap=await (await context.request.get(origin+'/sitemap.xml')).text();expect(sitemap).toContain('https://docs.onesa.eu/');expect(sitemap).not.toContain('localhost');expect(sitemap).not.toContain('/docs/ecosystem/');
 const publicRoutes=[...new Set([...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match=>new URL(match[1]).pathname))];
 expect(publicRoutes.length).toBeGreaterThan(10);
 for(const mode of ['light','dark']){
  await page.evaluate(mode=>sessionStorage.setItem('onesa-test-hour',mode==='dark'?'20':'12'),mode);
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
  for(const url of new Set(links)){expect((await context.request.get(origin+url.split('#')[0])).status(),`Broken public link: ${url}`).toBe(200);evidence.links++;}
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
 expect(errors).toEqual([]);console.log(JSON.stringify({result:'PASS',...evidence},null,2));
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
