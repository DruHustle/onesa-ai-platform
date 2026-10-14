// Browser fixture verification only: no hosted authorization or production PASS is inferred.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const require=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/docs/package.json'));
const {chromium,expect}=require('@playwright/test');
const chatRequire=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/chat/package.json'));
const {default:AxeBuilder}=chatRequire('@axe-core/playwright');
const internal=path.join(root,'onesa-ai-platform-frontend/apps/docs/build-internal');
const publicBuild=path.join(root,'onesa-ai-platform-frontend/apps/docs/build-public');
const types={'.html':'text/html','.js':'application/javascript','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.pdf':'application/pdf','.css':'text/css','.ico':'image/x-icon','.mmd':'text/plain'};
const navigation=JSON.parse(await fs.readFile(path.join(internal,'generated/engineering-navigation.json'),'utf8'));
const catalog=JSON.parse(await fs.readFile(path.join(internal,'generated/diagrams.json'),'utf8'));
for(const forbidden of ['docs/architecture/ONESA_DESIGN_SYSTEM.html','docs/operations/TAILSCALE_ADMINISTRATION.html','generated/diagrams/onesa-design-system.svg','generated/diagrams/tailscale-administration.pdf','onboarding.html','generated/engineering-navigation.json','generated/diagrams/ecosystem-current.svg','docs/onboarding/START_HERE.html'])await expect(fs.stat(path.join(publicBuild,forbidden))).rejects.toThrow();
const browser=await chromium.launch();
const context=await browser.newContext();
const fixture='https://onesa-engineering.test';
await context.route('**/*',async route=>{
 const url=new URL(route.request().url());if(url.origin!==fixture){await route.abort();return;}
 const relative=decodeURIComponent(url.pathname);
 const requested=path.resolve(internal,'.'+relative);
 if(!requested.startsWith(internal+path.sep)&&requested!==internal){await route.fulfill({status:404,body:'Not found'});return;}
 for(const candidate of [requested,path.join(requested,'index.html'),requested+'.html']){
  try{if((await fs.stat(candidate)).isFile()){await route.fulfill({status:200,contentType:types[path.extname(candidate)]||'application/octet-stream',body:await fs.readFile(candidate)});return;}}catch{}
 }
 await route.fulfill({status:404,body:'Not found'});
});
await context.addInitScript(()=>{Date.prototype.getHours=()=>12;});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const results={kind:'isolated-browser-fixture',hosted_access_verified:false,diagrams:0,chapters:navigation.chapters.length,learning_days:0,layouts:[],accessibility:[]};
try{
 for(const mode of ['light','dark'])for(const width of [320,768,1440])for(const route of ['/','/architecture','/onboarding']){
  await page.emulateMedia({colorScheme:mode});
  await page.setViewportSize({width,height:900});await page.goto(fixture+route);
  await expect(page.locator('main').first()).toBeVisible();await expect(page.locator('html')).toHaveAttribute('data-theme',mode);
  if(route==='/architecture'||route==='/onboarding')await expect(page.locator('.diagram-canvas svg').first()).toBeVisible();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);expect(overflow,`${route} ${width} ${mode}`).toBe(false);
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  const blocking=axe.violations.filter(v=>['critical','serious'].includes(v.impact));expect(blocking.map(v=>({id:v.id,targets:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),`${route} ${mode} ${width}`).toEqual([]);
  results.layouts.push({route,mode,width,overflow});results.accessibility.push({route,mode,width,blocking:0,advisory:axe.violations.length});
 }
 await page.setViewportSize({width:1440,height:1000});await page.goto(fixture+'/');
 const navLinks=await page.locator('.navbar__items:not(.navbar__items--right) a.navbar__link').allTextContents();
 const architectureIndex=navLinks.indexOf('Architecture & Workflows');expect(architectureIndex).toBeGreaterThanOrEqual(0);expect(navLinks[architectureIndex+1]).toBe('Engineering Onboarding');
 await page.goto(fixture+'/architecture');await expect(page.locator('.workflow-index button')).toHaveCount(navigation.architecture.length);
 for(const topic of navigation.architecture){await page.getByRole('button',{name:topic.title,exact:true}).click();await expect(page.locator('.diagram-canvas svg')).toBeVisible();await expect(page.locator('.diagram-panel')).toContainText(catalog.find(d=>d.id===topic.diagram).title);results.diagrams++;}
 await page.getByLabel('Zoom in',{exact:true}).click();await expect(page.locator('.diagram-canvas > div')).toHaveAttribute('style',/1.25/);
 await page.locator('.diagram-canvas').focus();await page.keyboard.press('ArrowRight');await expect(page.locator('.diagram-canvas > div')).toHaveAttribute('style',/30px/);
 await page.getByRole('button',{name:'Enlarge diagram',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');await expect(page.locator('.diagram-panel.expanded')).toHaveCount(0);
 for(const diagram of catalog)for(const extension of ['svg','png','pdf','mmd'])expect((await fs.stat(path.join(internal,'generated/diagrams',diagram.id+'.'+extension))).size).toBeGreaterThan(20);
 await page.goto(fixture+'/onboarding');await expect(page.locator('.learning-stage')).toHaveCount(4);await expect(page.locator('.learning-stage .diagram-canvas svg')).toHaveCount(4);
 await page.locator('.learning-checkpoints input').first().check();await page.locator('.learning-checkpoints input').first().focus();await page.emulateMedia({colorScheme:'light'});await expect(page.locator('.learning-checkpoints input').first()).toBeChecked();await expect(page.locator('.learning-checkpoints input').first()).toBeFocused();await page.emulateMedia({colorScheme:'dark'});await expect(page.locator('.learning-checkpoints input').first()).toBeChecked();await page.reload();await expect(page.locator('.learning-checkpoints input').first()).toBeChecked();
 for(const day of navigation.days){await expect(page.locator('#day-'+day.id)).toContainText(day.title);await expect(page.locator('#day-'+day.id+' .learning-checkpoints input')).toHaveCount(day.checkpoints.length);results.learning_days++;}
 for(const entry of [...navigation.architecture,...navigation.chapters,...navigation.days])expect((await fs.stat(path.join(internal,entry.url+'.html'))).isFile()).toBe(true);
 await page.getByLabel('Search documentation').fill('Day 4');await expect(page.locator('.search-results a').first()).toBeVisible();await page.keyboard.press('Escape');
 await page.goto(fixture+'/docs/onboarding/START_HERE');await expect(page.locator('.theme-doc-sidebar-container')).toContainText('Architecture & Workflows');await expect(page.locator('.theme-doc-sidebar-container')).toContainText('Engineering Onboarding');
 expect(errors).toEqual([]);console.log(JSON.stringify({result:'PASS',...results},null,2));
}finally{await browser.close();}
