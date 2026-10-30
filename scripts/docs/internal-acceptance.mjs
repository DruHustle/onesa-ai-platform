// Complete read-only engineering UI observations; no hosted authority is created here.
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {waitForInteractiveDocumentation} from './acceptance.mjs';
const require=createRequire(new URL('../../onesa-ai-platform-frontend/apps/docs/package.json',import.meta.url));
const {expect}=require('@playwright/test');
const {default:AxeBuilder}=require('@axe-core/playwright');

export async function validateProtectedDocumentation({page,get,origin,revision,environment,registry,icons}){
 const errors=[],error=e=>errors.push(e.name);page.on('pageerror',error);
 const result={origin,environment_context:environment,layouts:[],accessibility:[],architecture:[],chapters:[],learning_days:[],application_navigation:[],icons:[],api_reference:[],links_checked:0};
 const visited=new Set();
 const json=async route=>{const r=await get(origin+route);expect(r.status()).toBe(200);expect(r.headers()['content-type']).toContain('application/json');return r.json();};
 const visit=async route=>{const r=await page.goto(origin+route,{waitUntil:'domcontentloaded'});expect(r.status()).toBe(200);await expect(page.locator('main').first()).toBeVisible();await waitForInteractiveDocumentation(page);visited.add(route);};
 try{
  const provenance=await json('/generated/provenance.json');
  expect(provenance.classification).toBe('internal');expect(provenance.revision).toBe(revision);
  result.provenance={revision:provenance.revision,classification:provenance.classification};
  const navigation=await json('/generated/engineering-navigation.json'),catalog=await json('/generated/diagrams.json');
  expect(navigation.architecture).toHaveLength(18);expect(navigation.chapters).toHaveLength(17);expect(navigation.days).toHaveLength(4);expect(catalog).toHaveLength(87);
  const audience=(environment==='production'?'':environment.toUpperCase()+' · ')+'Internal Engineering · Authorized access';
  for(const mode of ['light','dark'])for(const width of [320,768,1440])for(const route of ['/','/architecture','/onboarding']){
   await page.emulateMedia({colorScheme:mode});await page.setViewportSize({width,height:900});await visit(route);
   await expect(page.locator('html')).toHaveAttribute('data-theme',mode);await expect(page.locator('.docs-audience')).toHaveText(audience);await expect(page.locator('.appearance-control')).toHaveCount(0);
   const diagram=route!=='/';if(diagram)await expect(page.locator('.diagram-canvas svg').first()).toBeVisible();
   expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)).toBe(false);
   const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
   expect(audit.violations.filter(v=>['critical','serious'].includes(v.impact))).toEqual([]);
   result.layouts.push({route,mode,width,overflow:false,diagram_visible:diagram});
   result.accessibility.push({route,mode,width,violations:audit.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))});
  }
  await page.setViewportSize({width:1440,height:900});await visit('/architecture');
  await expect(page.locator('.workflow-index button')).toHaveCount(navigation.architecture.length);
  for(const topic of navigation.architecture){await page.getByRole('button',{name:topic.title,exact:true}).click();await expect(page.locator('.diagram-canvas svg')).toBeVisible();await expect(page.locator('.diagram-panel')).toContainText(catalog.find(d=>d.id===topic.diagram).title);result.architecture.push({diagram:topic.diagram,url:topic.url,visible:true});}
  await page.getByLabel('Zoom in',{exact:true}).click();await expect(page.locator('.diagram-canvas > div')).toHaveAttribute('style',/1.25/);
  await page.locator('.diagram-canvas').focus();await page.keyboard.press('ArrowRight');await expect(page.locator('.diagram-canvas > div')).toHaveAttribute('style',/30px/);
  await page.getByRole('button',{name:'Enlarge diagram',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');await expect(page.locator('.diagram-panel.expanded')).toHaveCount(0);
  result.diagram_controls={zoom:true,keyboard_pan:true,dialog:true,escape:true};
  await visit('/onboarding');await expect(page.locator('.learning-stage')).toHaveCount(4);
  // Keep progress values within this owned target and compare only a boolean.
  // No checkpoint is clicked, no storage is exported or written by the observer.
  await page.evaluate(()=>{globalThis.__onesaOwnedLearningBefore=localStorage.getItem('onesa-engineering-learning-v1');});
  const progress=await page.locator('.learning-checkpoints input').evaluateAll(nodes=>nodes.map(n=>n.checked));
  for(const day of navigation.days){await expect(page.locator('#day-'+day.id)).toContainText(day.title);await expect(page.locator('#day-'+day.id+' .learning-checkpoints input')).toHaveCount(day.checkpoints.length);result.learning_days.push({id:day.id,checkpoints:day.checkpoints.length});}
  await page.locator('.learning-checkpoints input').first().focus();await page.emulateMedia({colorScheme:'light'});await page.emulateMedia({colorScheme:'dark'});await expect(page.locator('.learning-checkpoints input').first()).toBeFocused();
  expect(await page.locator('.learning-checkpoints input').evaluateAll(nodes=>nodes.map(n=>n.checked))).toEqual(progress);
  expect(await page.evaluate(()=>globalThis.__onesaOwnedLearningBefore===localStorage.getItem('onesa-engineering-learning-v1'))).toBe(true);
  await page.reload({waitUntil:'domcontentloaded'});await waitForInteractiveDocumentation(page);
  expect(await page.locator('.learning-checkpoints input').evaluateAll(nodes=>nodes.map(n=>n.checked))).toEqual(progress);
  result.existing_progress_preserved=true;result.progress_mutations=0;
  for(const chapter of navigation.chapters){await visit(chapter.url);result.chapters.push({url:chapter.url,http_status:200});}
  await page.getByLabel('Search documentation').fill('Day 4');await expect(page.locator('.search-results a').first()).toBeVisible();await page.keyboard.press('Escape');result.search={query:'Day 4',results_visible:true};
  await visit('/docs/onboarding/START_HERE');
  result.sidebar=await page.locator('.theme-doc-sidebar-container .menu__list').first().evaluate(list=>[...list.children].map(item=>item.querySelector('.menu__link')?.textContent?.trim()).slice(0,6));
  expect(result.sidebar).toEqual(['Start here','Product guides','Tutorials','API','Architecture','Troubleshooting and releases']);
  const expectedLinks=registry.applications.map(app=>({label:app.label,href:app.href.replace(/\/$/,'')}));
  for(const view of ['desktop','mobile']){
   await page.setViewportSize({width:view==='desktop'?1440:390,height:900});await visit('/');let dropdown;
   if(view==='mobile'){await page.getByRole('button',{name:'Toggle navigation bar',exact:true}).click();dropdown=page.locator('.navbar-sidebar .menu__list-item').filter({has:page.getByRole('button',{name:'Onesa applications',exact:true})});await dropdown.getByRole('button',{name:'Onesa applications',exact:true}).click();}
   else{dropdown=page.locator('.navbar__items .dropdown').filter({has:page.getByRole('button',{name:'Onesa applications',exact:true})});await dropdown.getByRole('button',{name:'Onesa applications',exact:true}).press('Enter');}
   const menu=dropdown.locator(view==='mobile'?':scope > .menu__list':'.dropdown__menu');await expect(menu).toBeVisible();
   const actual=await menu.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>({label:n.textContent.trim(),href:n.getAttribute('href').replace(/\/$/,'')})));
   expect(actual).toEqual(expectedLinks);result.application_navigation.push({view,links:actual});
   if(view==='mobile')await page.getByRole('button',{name:'Close navigation bar',exact:true}).click();else await dropdown.getByRole('button',{name:'Onesa applications',exact:true}).press('Enter');
  }
  for(const name of ['onesa-docs.svg','onesa-docs.ico','onesa-docs-180.png']){
   const item=icons.products[0].files.find(x=>x.name===name),route=name.endsWith('.ico')?'/favicon.ico':'/brand/icons/v1/'+name;
   const response=await get(origin+route);expect(response.status()).toBe(200);expect(createHash('sha256').update(await response.body()).digest('hex')).toBe(item.sha256);result.icons.push({path:route,sha256:item.sha256});
  }
  await page.setViewportSize({width:1440,height:900});await visit('/api-explorer');
  for(const product of ['ai','portal','robot']){expect((await get(origin+(product==='ai'?'/generated/openapi.json':'/generated/openapi-'+product+'.json'))).status()).toBe(200);await page.getByLabel('API product').selectOption(product);await expect(page.locator('.swagger-ui .opblock').first()).toBeVisible();await expect(page.getByRole('button',{name:'Try it out',exact:true})).toHaveCount(0);result.api_reference.push({product,source_status:200,swagger_visible:true,execution_controls:0});}
  await visit('/assistant');await expect(page.getByRole('heading',{name:'Documentation assistant unavailable',exact:true})).toBeVisible();await expect(page.locator('main form')).toHaveCount(0);result.assistant={available:false,form_count:0,network_mutations:0};
  const manuals=await json('/generated/manuals.json');expect(manuals).toHaveLength(22);
  for(const manual of manuals){expect(manual.classification).toBe('internal');const r=await get(origin+'/generated/manuals/'+encodeURIComponent(manual.file));expect(r.status()).toBe(200);expect((await r.body()).subarray(0,5).toString()).toBe('%PDF-');}result.manuals=manuals.length;
  // Every artifact byte is checked separately; also follow the UI's actual local links.
  for(const route of visited){await visit(route);const links=await page.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')).filter(x=>x?.startsWith('/')&&!x.startsWith('//')));for(const link of new Set(links)){expect((await get(origin+link.split('#')[0])).status(),'Broken protected link '+link+' from '+route).toBe(200);result.links_checked++;}}
  expect(errors).toEqual([]);return {...result,javascript_errors:errors,result:'PASS'};
 }finally{page.off('pageerror',error);}
}
