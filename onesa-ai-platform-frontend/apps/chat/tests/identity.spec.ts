import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test('sign-in and identity pages fit 320px and expose labelled controls',async({page})=>{
 for(const route of ['/','/recovery','/invitation']){
  await page.setViewportSize({width:320,height:760});await page.goto(route);
  await expect(page.locator('main')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()).violations).toEqual([]);
 }
 await expect(page.locator('main').getByRole('alert')).toContainText('An invitation is required');
});
test('bootstrap outage is distinguishable from an anonymous session and supports retry',async({page})=>{
 await page.route('**/api/v1/auth/me',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'unavailable',message:'Synthetic dependency outage'}})}));
 await page.goto('/');await expect(page.locator('main').getByRole('alert')).toBeVisible();
 await expect(page.getByRole('button',{name:/retry/i})).toBeVisible();
 await page.unroute('**/api/v1/auth/me');await page.getByRole('button',{name:/retry/i}).click();
 await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
});
test('recovery clears the link fragment and reports actual queue failures',async({page})=>{
 const token='a'.repeat(64);let observed='';
 await page.route('**/api/v1/auth/recovery/complete',async route=>{observed=route.request().postDataJSON().token;await route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:{code:'invalid_token',message:'Recovery link is expired or invalid'}})});});
 await page.goto('/recovery#token='+token);await expect(page.getByLabel('New password')).toBeVisible();
 expect(new URL(page.url()).hash).toBe('');await page.getByLabel('New password').fill('synthetic-reset-password-123!');await page.getByRole('button',{name:'Set new password'}).click();
 await expect(page.getByRole('status')).toContainText('expired or invalid');expect(observed).toBe(token);
 await page.route('**/api/v1/auth/recovery/request',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'mail_disabled',message:'Recovery delivery is unavailable'}})}));
 await page.goto('/recovery');await page.getByLabel('Email').fill('fixture@example.test');await page.getByRole('button',{name:'Request recovery'}).click();
 await expect(page.getByRole('status')).toContainText('unavailable');await expect(page.getByRole('status')).not.toContainText('queued');
});
