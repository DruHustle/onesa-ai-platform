/* Real protected Preview browser checks; private fixture credentials stay on the runner. */
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const requireChat = createRequire(path.resolve('onesa-ai-platform-frontend/apps/chat/package.json'));
const {chromium, expect} = requireChat('@playwright/test');
const {default: AxeBuilder} = requireChat('@axe-core/playwright');

async function main() {
  if (process.env.GITHUB_REF !== 'refs/heads/staging' || process.env.GITHUB_REPOSITORY !== 'DruHustle/onesa-ai-platform') throw new Error('Only AI staging is authorized');
  const {origin, accounts} = JSON.parse(fs.readFileSync('/tmp/onesa-staging-acceptance-users.json', 'utf8'));
  const bypass = process.env.VERCEL_AUTOMATION_BYPASS_SECRET;
  if (!bypass || !origin.startsWith('https://') || !new URL(origin).hostname.endsWith('.vercel.app')) throw new Error('Protected Preview fixture unavailable');
  const browser = await chromium.launch();
  const evidence = [];
  try {
    for (const [name, width, height] of [['desktop',1440,900], ['tablet',768,1024], ['mobile',390,844]]) {
      const context = await browser.newContext({viewport:{width,height}, locale:'en-US'});
      // Send the protection credential only to this verified Preview host.
      await context.route('**/*', async route => {
        const request = route.request();
        await route.continue({headers: {...request.headers(), ...(new URL(request.url()).origin === origin ? {'x-vercel-protection-bypass': bypass} : {})}});
      });
      const page = await context.newPage();
      await page.goto(origin, {waitUntil:'networkidle'});
      await expect(page.getByLabel('Email', {exact:true})).toBeVisible();
      await page.getByLabel('Email', {exact:true}).fill(accounts[0].email);
      await page.getByLabel('Password', {exact:true}).fill(accounts[0].password);
      await page.getByRole('button', {name:'Sign in',exact:true}).click();
      await expect(page.getByLabel('Message Onesa AI')).toBeVisible();
      for (const route of ['/', '/knowledge', '/agents', '/travel', '/settings']) {
        console.log(JSON.stringify({viewport:name, route, check:'render-and-accessibility'}));
        const response = await page.goto(origin + route, {waitUntil:'networkidle'});
        if (!response || response.status() !== 200) throw new Error('Interface route failed');
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
        if (overflow) throw new Error('Horizontal overflow on ' + name + route);
        const violations = (await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations.filter(item => ['critical','serious'].includes(item.impact));
        if (violations.length) throw new Error('Accessibility issues: ' + violations.map(item => item.id).join(','));
      }
      const links = await page.locator('a[href]').evaluateAll(nodes => nodes.map(node => node.getAttribute('href')));
      if (!links.some(link => link && link.startsWith('https://docs.onesa.eu'))) throw new Error('Documentation link unavailable');
      evidence.push({viewport:name, routes:['/','/knowledge','/agents','/travel','/settings'], login:'PASS', overflow:'PASS', automated_accessibility:'PASS'});
      await context.close();
    }
    const report = {commit:process.env.GITHUB_SHA, origin, browser:'chromium', responsive_checks:evidence, manual_accessibility_review:'REQUIRED'};
    fs.writeFileSync('/tmp/onesa-staging-ui.json', JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  } finally {
    await browser.close();
    fs.rmSync('/tmp/onesa-staging-acceptance-users.json', {force:true});
  }
}
main().catch(() => {console.error('Hosted staging browser verification failed; inspect selectors, deployment protection and scoped application configuration. No fixture credentials logged.');process.exitCode=1;});
