// Hold real static-build JavaScript to reproduce the SSR keyboard-readiness race.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {waitForInteractiveDocumentation} from './acceptance.mjs';
const app=path.resolve('onesa-ai-platform-frontend/apps/docs'),build=path.join(app,'build-public');
const require=createRequire(path.join(app,'package.json')),{chromium,expect}=require('@playwright/test');
const origin='https://onesa-docs-readiness.test';

test('keyboard acceptance waits for actual hydration, then checks one Enter; missing hydration fails',async t=>{
 const browser=await chromium.launch();t.after(()=>browser.close());
 const context=await browser.newContext({serviceWorkers:'block'});let release;
 const held=new Promise(resolve=>{release=resolve;});let scriptRequests=0;
 await context.route('**/*',async route=>{
  const url=new URL(route.request().url());assert.equal(url.origin,origin);
  assert.equal(route.request().method(),'GET');
  const pathname=decodeURIComponent(url.pathname);
  const requested=path.resolve(build,'.'+pathname);
  assert.ok(requested.startsWith(build+path.sep)||requested===build);
  if(pathname.endsWith('.js')){scriptRequests++;await held;}
  let body,file;
  for(const candidate of [requested,path.join(requested,'index.html'),requested+'.html']){
   try{if((await fs.stat(candidate)).isFile()){file=candidate;body=await fs.readFile(file);break;}}catch{}
  }
  if(!body)return route.fulfill({status:404,body:'Not found'});
  const mime={'.html':'text/html','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.json':'application/json'};
  await route.fulfill({status:200,contentType:mime[path.extname(file)]||'application/octet-stream',body});
 });
 const page=await context.newPage();await page.goto(origin+'/',{waitUntil:'commit'});
 const button=page.locator('.navbar__items .dropdown').getByRole('button',{name:'Onesa applications',exact:true});
 await expect(button).toBeVisible();
 assert.notEqual(await page.locator('html').getAttribute('data-has-hydrated'),'true');
 // This is the old acceptance sequence: visible SSR markup cannot receive React keys.
 await button.press('Enter');assert.equal(await button.getAttribute('aria-expanded'),'false');
 await assert.rejects(waitForInteractiveDocumentation(page,100));
 assert.ok(scriptRequests>0);
 // Release the same real build, without retries, injected handlers or state changes.
 release();await waitForInteractiveDocumentation(page);
 await button.press('Enter');await expect(button).toHaveAttribute('aria-expanded','true');
 await expect(page.locator('.navbar__items .dropdown__menu').filter({hasText:'Onesa UG'})).toBeVisible();
 await button.press('Enter');await expect(button).toHaveAttribute('aria-expanded','false');
});
