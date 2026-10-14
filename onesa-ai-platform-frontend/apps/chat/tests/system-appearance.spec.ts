import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Isolated browser fixtures exercise production UI; they do not qualify backend auth/inference.
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith('/auth/me') ? { id: 'synthetic-user', display_name: 'Synthetic design fixture', email: 'synthetic@example.com' }
      : path.endsWith('/documentation/access') ? { engineering: false }
      : path.endsWith('/models') ? { items: [{ backend: 'mock', model_identifier: 'synthetic-design-fixture', real_inference: false }] }
      : path.endsWith('/conversations') && route.request().method() === 'POST' ? { id: 'fixture-conversation', title: 'Synthetic stream' }
      : path.endsWith('/conversations/fixture-conversation') ? { messages: [{ id: 'synthetic-message', role: 'assistant', content: { text: 'Synthetic stream completed' } }] }
      : { items: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
});

for (const mode of ['light', 'dark'] as const) test(`system ${mode}: independent clock, identity and representative routes`, async ({ page }, info) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(hour => { Date.prototype.getHours = () => hour; localStorage.setItem('onesa-unrelated-fixture', 'preserved'); }, mode === 'dark' ? 12 : 23);
  await page.emulateMedia({ colorScheme: mode, reducedMotion: 'reduce' });
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [route, title] of [['/', 'Chat'], ['/knowledge', 'Knowledge'], ['/agents', 'Agents'], ['/travel', 'Travel']]) {
      await page.goto(route);
      await expect(page.locator('main')).toBeVisible();
      if (route === '/') await expect(page.getByLabel('Message Onesa AI')).toBeVisible();
      await expect(page).toHaveTitle(`${title} | Onesa AI Platform`);
      expect(await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe(mode);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      const violations = (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()).violations;
      expect(violations.map(v => ({ id: v.id, impact: v.impact, targets: v.nodes.map(n => n.target) }))).toEqual([]);
      if (width === 390 || width === 1440) await page.screenshot({ path: info.outputPath(`${title.toLowerCase()}-${mode}-${width}.png`), fullPage: true });
    }
  }
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => localStorage.getItem('onesa-unrelated-fixture'))).toBe('preserved');
});

test('live system change preserves focused chat and feature drafts without application requests', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto('/');
  const draft = page.getByLabel('Message Onesa AI');
  await expect(draft).toBeVisible();
  await draft.fill('Keep this unsent synthetic draft');
  await draft.focus();
  const requests: string[] = [];
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) requests.push(request.url()); });
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(draft).toHaveValue('Keep this unsent synthetic draft');
  await expect(draft).toBeFocused();
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe('dark');
  await page.goto('/travel');
  await page.getByLabel('Destination', { exact: true }).fill('Synthetic destination draft');
  await page.getByLabel('Destination', { exact: true }).focus();
  await page.waitForLoadState('networkidle');
  requests.length = 0;
  await page.emulateMedia({ colorScheme: 'light', forcedColors: 'active' });
  await expect(page.getByLabel('Destination', { exact: true })).toHaveValue('Synthetic destination draft');
  await expect(page.getByLabel('Destination', { exact: true })).toBeFocused();
  expect(requests).toEqual([]);
  expect(await page.evaluate(() => Object.keys(localStorage).filter(key => /theme|appearance/i.test(key)))).toEqual([]);
});

test('preference change keeps a synthetic active stream alive without resubmission', async ({ page }) => {
  await page.addInitScript(() => {
    const original = window.fetch.bind(window);
    Object.assign(window, { appearanceFixtureStreams: 0 });
    window.fetch = async (input, init) => {
      if (String(input) !== '/api/v1/chat/completions') return original(input, init);
      const state = window as unknown as { appearanceFixtureStreams: number };
      state.appearanceFixtureStreams += 1;
      const encoder = new TextEncoder();
      return new Response(new ReadableStream({
        async start(controller) {
          const frame = (event: string, data: unknown) => controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
          frame('message_start', { conversation_id: 'fixture-conversation', run_id: 'synthetic-run' });
          for (let i = 0; i < 20; i++) {
            await new Promise(resolve => setTimeout(resolve, 100));
            frame('content_delta', { text: 'synthetic ' });
          }
          frame('message_end', { message_id: 'synthetic-message', model: { backend: 'mock', model_identifier: 'synthetic-design-fixture', real_inference: false } });
          controller.close();
        },
      }), { headers: { 'Content-Type': 'text/event-stream' } });
    };
  });
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto('/');
  await page.getByLabel('Message Onesa AI').fill('Synthetic appearance stream');
  await page.getByLabel('Send message').click();
  await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeVisible();
  await expect(page.locator('.message').filter({ hasText: 'Generating' })).toContainText('synthetic');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeVisible();
  await expect(page.locator('.message.assistant')).toContainText('Synthetic stream completed');
  expect(await page.evaluate(() => (window as unknown as { appearanceFixtureStreams: number }).appearanceFixtureStreams)).toBe(1);
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe('dark');
});
