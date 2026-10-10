import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const widths=[320,390,768,1024,1440];
test('release audit: responsive authenticated views, reduced motion and axe',async({page,baseURL},info)=>{
 test.setTimeout(90000);
 const created=await page.request.post(`${baseURL}/api/v1/auth/register`,{headers:{Origin:baseURL!},data:{email:`layout-${info.project.name}-${Date.now()}@example.com`,password:'layout-synthetic-password-123!',display_name:'Layout fixture'}});
 expect(created.status()).toBe(201);
 await page.emulateMedia({reducedMotion:'reduce'});
 for(const width of widths){
  await page.setViewportSize({width,height:900});
  for(const route of ['/','/knowledge','/agents','/travel']){
   const response=await page.goto(route);
   const policy=response?.headers()['content-security-policy']||'';
   expect(policy).toContain("'nonce-");expect(policy).toContain("frame-ancestors 'none'");
   expect(policy).not.toContain("'unsafe-eval'");

   await expect(page.locator('main')).toBeVisible();
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
   const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()).violations;
   expect(violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))).toEqual([]);
   await page.screenshot({path:info.outputPath(`view-${width}-${route.replaceAll('/','')||'chat'}.png`),fullPage:true});
  }
 }
 await page.goto('/');await expect(page.getByLabel('Message Onesa AI')).toBeVisible();await page.keyboard.press('Tab');
 expect(await page.evaluate(()=>document.activeElement!==document.body)).toBe(true);
});
