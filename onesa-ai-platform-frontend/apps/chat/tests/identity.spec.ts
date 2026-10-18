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

for (const invitation of [false, true]) {
 const route = invitation ? '/invitation' : '/recovery';
 const action = invitation ? 'Create invited account' : 'Set new password';
 const endpoint = invitation ? '**/api/v1/auth/register' : '**/api/v1/auth/recovery/complete';
 const field = invitation ? 'invitation_token' : 'token';
 test(`${route}: initial and same-document tokens stay in memory, exact submits and expired/repeated links`, async ({page}) => {
  await page.setViewportSize({width:320,height:760});
  const first='a'.repeat(64), second='b'.repeat(64), submitted:string[]=[];
  await page.route(endpoint, async intercepted => {
   submitted.push(intercepted.request().postDataJSON()[field]);
   await intercepted.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:{code:'invalid_token',message:'Link expired or invalid'}})});
  });
  await page.goto(route+'?source=synthetic#token='+first);
  await expect(page.getByLabel('New password')).toBeVisible();
  await expect.poll(()=>new URL(page.url()).hash).toBe('');
  expect(new URL(page.url()).search).toBe('?source=synthetic');expect(submitted).toEqual([]);
  const submit=async()=>{
   if(invitation){await page.getByLabel('Email',{exact:true}).fill('fixture@example.test');await page.getByLabel('Display name').fill('Synthetic');}
   await page.getByLabel('New password').fill('synthetic-password-123!');
   await page.getByRole('button',{name:action,exact:true}).click();
   await expect(page.getByRole('status')).toContainText('expired or invalid');
  };
  await submit();expect(submitted).toEqual([first]);
  await page.evaluate(value=>{window.location.hash='token='+value;},second);
  await expect.poll(()=>new URL(page.url()).hash).toBe('');
  await expect(page.getByRole('status')).toBeEmpty();await submit();expect(submitted).toEqual([first,second]);
  await page.evaluate(value=>{window.location.hash='token='+value;},second);
  await expect.poll(()=>new URL(page.url()).hash).toBe('');await submit();expect(submitted).toEqual([first,second,second]);
  await page.goto(route);if(!invitation)await expect(page.getByRole('button',{name:'Request recovery'})).toBeVisible();
  else await expect(page.locator('main').getByRole('alert')).toContainText('invitation is required');
  await page.evaluate(value=>{window.location.hash='token='+value;},first);
  await expect(page.getByRole('button',{name:action,exact:true})).toBeVisible();
  await expect.poll(()=>new URL(page.url()).hash).toBe('');expect(submitted).toHaveLength(3);
  await submit();expect(submitted).toEqual([first,second,second,first]);
 });
 test(`${route}: a new link invalidates a pending response without submitting again`,async({page})=>{
  let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve;});let requests=0;
  await page.route(endpoint,async intercepted=>{
   requests++;await gate;await intercepted.fulfill({status:200,contentType:'application/json',body:'{}'}).catch(()=>{});
  });
  await page.goto(route+'#token='+'c'.repeat(64));
  if(invitation){await page.getByLabel('Email',{exact:true}).fill('fixture@example.test');await page.getByLabel('Display name').fill('Synthetic');}
  await page.getByLabel('New password').fill('synthetic-password-123!');await page.getByRole('button',{name:action,exact:true}).click();
  await expect.poll(()=>requests).toBe(1);
  await page.evaluate(()=>{window.location.hash='token='+'d'.repeat(64);});
  await expect(page.getByRole('button',{name:action,exact:true})).toBeEnabled();release();
  await expect.poll(()=>new URL(page.url()).hash).toBe('');await expect(page.getByRole('status')).toBeEmpty();
  await expect(page.getByLabel('New password')).toBeVisible();expect(new URL(page.url()).pathname).toBe(route);expect(requests).toBe(1);
 });
}
