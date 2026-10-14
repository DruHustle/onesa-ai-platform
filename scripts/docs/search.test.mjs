import test, {before, after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const app = path.join(root, 'onesa-ai-platform-frontend/apps/docs');
const require = createRequire(path.join(app, 'package.json'));
const {build, transform} = require('esbuild');
const {chromium, expect} = require('@playwright/test');
const origin = 'https://onesa-search.test';
const entries = [
  {title: 'Authentication guide', url: '/docs/auth', text: 'Sessions and engineering access.'},
  {title: 'API reference', url: '/docs/api', text: 'Authentication and session examples.'},
];
let browser, script, helpers;

before(async () => {
  const transformed = await transform(await readFile(path.join(app, 'src/lib/search-index.ts'), 'utf8'),
    {loader: 'ts', format: 'esm'});
  helpers = await import('data:text/javascript;base64,' + Buffer.from(transformed.code).toString('base64'));
  const bundle = await build({
    absWorkingDir: app, bundle: true, write: false, format: 'iife',
    define: {'process.env.NODE_ENV': '"production"'},
    stdin: {resolveDir: app, loader: 'tsx', contents: `
      import React, {useState} from 'react';
      import {createRoot} from 'react-dom/client';
      import Search from './src/theme/SearchBar/index';
      window.searchStats = {fetches: 0, parses: 0, aborts: 0, credentials: []};
      const nativeFetch = window.fetch.bind(window);
      window.fetch = async (url, options) => {
        if (url !== '/generated/search.json') throw new Error('Unexpected fixture request');
        window.searchStats.fetches++;
        window.searchStats.credentials.push(options.credentials);
        options.signal.addEventListener('abort', () => window.searchStats.aborts++, {once: true});
        const response = await nativeFetch(url, options);
        const json = response.json.bind(response);
        response.json = () => {window.searchStats.parses++; return json();};
        return response;
      };
      function Fixture() {
        const [visible, setVisible] = useState(true);
        return <main><h1>Synthetic documentation search fixture</h1>{visible && <Search/>}
          <button type="button" onClick={() => setVisible(false)}>Remove fixture search</button></main>;
      }
      createRoot(document.getElementById('root')).render(<Fixture/>);`},
    plugins: [{name: 'fixture-link', setup(builder) {
      builder.onResolve({filter: /^@docusaurus\/Link$/}, () => ({path: 'link', namespace: 'fixture-link'}));
      builder.onLoad({filter: /.*/, namespace: 'fixture-link'}, () => ({resolveDir: app, loader: 'tsx',
        contents: `import React from 'react'; export default function Link({to, children, ...props}) {
          return <a href={to} {...props}>{children}</a>;
        }`}));
    }}],
  });
  script = bundle.outputFiles[0].text;
  browser = await chromium.launch();
});
after(async () => {await browser?.close();});

async function fixture(t, {status = 200, contentType = 'application/json', body = JSON.stringify(entries), held = false, olderSignalApi = false} = {}) {
  const context = await browser.newContext();
  t.after(() => context.close());
  if (olderSignalApi) await context.addInitScript(() => {
    delete AbortSignal.any;
    delete AbortSignal.timeout;
  });
  const errors = [], methods = [];
  let release;
  const gate = new Promise(resolve => {release = resolve;});
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    methods.push(request.method());
    assert.equal(url.origin, origin, 'The fixture cannot contact a live application or provider');
    if (url.pathname === '/generated/search.json') {
      if (held) await gate;
      await route.fulfill({status, contentType, body}).catch(() => {});
    } else if (url.pathname === '/fixture.js') {
      await route.fulfill({contentType: 'application/javascript', body: script});
    } else {
      await route.fulfill({contentType: 'text/html', body: '<!doctype html><html lang="en"><title>Search fixture</title><body><div id="root"></div><script src="/fixture.js"></script></body></html>'});
    }
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.name));
  await page.goto(origin);
  const input = page.getByLabel('Search documentation');
  await expect(input).toBeVisible();
  return {page, input, release, errors, methods,
    stats: () => page.evaluate(() => window.searchStats)};
}

test('normalization reads source entries once and preserves multi-term ranking, ties and result bounds', () => {
  let titleReads = 0, textReads = 0;
  const source = [{get title() {titleReads++; return 'AUTHENTICATION guide';}, url: '/docs/auth',
    get text() {textReads++; return 'Engineering Sessions';}}, entries[1]];
  const index = helpers.prepareSearchIndex(source);
  assert.deepEqual(helpers.searchDocumentation(index, ' authentication ' ).map(entry => entry.url), ['/docs/auth', '/docs/api']);
  assert.deepEqual(helpers.searchDocumentation(index, 'ENGINEERING sessions').map(entry => entry.url), ['/docs/auth']);
  assert.deepEqual(helpers.searchDocumentation(index, 'unknown'), []);
  assert.deepEqual(helpers.searchDocumentation(index, '  '), []);
  assert.equal(titleReads, 1);
  assert.equal(textReads, 1);
  assert.equal(index[0].text, 'Engineering Sessions', 'Display text is preserved');
  const many = helpers.prepareSearchIndex(Array.from({length: 12}, (_, i) => ({title: 'Tie', text: 'term', url: '/docs/' + i})));
  assert.deepEqual(helpers.searchDocumentation(many, 'term').map(entry => entry.url),
    Array.from({length: 8}, (_, i) => '/docs/' + i));
});

test('idle reading fetches nothing; first focus loads once and repeated activation reuses one parsed index', async t => {
  const f = await fixture(t, {held: true});
  await f.page.getByRole('button', {name: 'Remove fixture search'}).focus();
  await f.page.keyboard.press('Escape');
  await f.page.waitForTimeout(100);
  assert.deepEqual(await f.stats(), {fetches: 0, parses: 0, aborts: 0, credentials: []});
  await f.input.focus();
  await expect(f.page.getByRole('status')).toHaveText('Loading documentation search…');
  await f.input.fill('authentication');
  await f.page.keyboard.press('Escape');
  await expect(f.page.getByRole('region', {name: 'Search results'})).toHaveCount(0);
  await f.page.keyboard.press('Control+k');
  await expect(f.input).toBeFocused();
  assert.equal((await f.stats()).fetches, 1, 'Typing and reopening while loading cannot start parallel requests');
  f.release();
  await expect(f.page.locator('.search-results a')).toHaveText([
    'Authentication guideSessions and engineering access.…',
    'API referenceAuthentication and session examples.…',
  ]);
  await f.page.getByRole('button', {name: 'Close search'}).click();
  await expect(f.input).toBeFocused();
  await expect(f.page.getByRole('region', {name: 'Search results'})).toHaveCount(0);
  await f.page.keyboard.press('Meta+k');
  await f.input.fill('engineering sessions');
  await expect(f.page.locator('.search-results a')).toHaveCount(1);
  await f.input.fill('no-such-document');
  await expect(f.page.getByText('No matching documents.', {exact: true})).toBeVisible();
  await f.input.fill('');
  await expect(f.page.getByText('Type to search documentation.', {exact: true})).toBeVisible();
  assert.deepEqual(await f.stats(), {fetches: 1, parses: 1, aborts: 0, credentials: ['same-origin']});
  assert.deepEqual(f.errors, []);
  assert.ok(f.methods.every(method => method === 'GET'));
});

test('keyboard activation, Escape and Enter preserve the query and navigate to the best existing result', async t => {
  const f = await fixture(t);
  await f.page.keyboard.press('Control+k');
  await expect(f.input).toBeFocused();
  await f.input.fill('authentication');
  await expect(f.page.locator('.search-results a').first()).toHaveAttribute('href', '/docs/auth');
  await f.page.locator('.search-results a').first().focus();
  await f.page.keyboard.press('Escape');
  await expect(f.input).toBeFocused();
  await expect(f.input).toHaveValue('authentication');
  await f.page.keyboard.press('Meta+k');
  await expect(f.input).toBeFocused();
  assert.equal((await f.stats()).fetches, 1);
  await f.page.keyboard.press('Enter');
  await expect(f.page).toHaveURL(origin + '/docs/auth');
  assert.deepEqual(f.errors, []);
  assert.ok(f.methods.every(method => method === 'GET'));
});

for (const response of [
  {name: 'expired private access', status: 401, contentType: 'text/html', body: '<h1>Sign in</h1>'},
  {name: 'an HTML access redirect', status: 200, contentType: 'text/html', body: '<h1>Sign in</h1>'},
  {name: 'invalid JSON', status: 200, contentType: 'application/json', body: '{'},
  {name: 'an invalid index', status: 200, contentType: 'application/json', body: '[{"title":"Incomplete"}]'},
]) test(`${response.name} shows a truthful error without results, retry loops or losing the draft`, async t => {
  const f = await fixture(t, response);
  await f.input.fill('authentication');
  await expect(f.page.getByRole('alert')).toHaveText('Documentation search is unavailable. Sign in again or reload.');
  await expect(f.page.getByRole('status')).toHaveCount(0);
  await expect(f.page.locator('.search-results a')).toHaveCount(0);
  await f.page.keyboard.press('Escape');
  await f.page.keyboard.press('Control+k');
  await expect(f.input).toHaveValue('authentication');
  await expect(f.page.getByRole('alert')).toBeVisible();
  assert.equal((await f.stats()).fetches, 1);
  assert.deepEqual(f.errors, []);
  assert.ok(f.methods.every(method => method === 'GET'));
});

test('unmount cancels the activated fetch without updating a removed search', async t => {
  const f = await fixture(t, {held: true});
  await f.input.focus();
  await expect(f.page.getByRole('status')).toBeVisible();
  await f.page.getByRole('button', {name: 'Remove fixture search'}).click();
  await expect(f.input).toHaveCount(0);
  assert.equal((await f.stats()).aborts, 1);
  f.release();
  assert.deepEqual(f.errors, []);
});

test('without newer AbortSignal helpers, a stalled index reaches a bounded error and preserves the editable query', async t => {
  const f = await fixture(t, {held: true, olderSignalApi: true});
  assert.deepEqual(await f.page.evaluate(() => [typeof AbortSignal.any, typeof AbortSignal.timeout]), ['undefined', 'undefined']);
  await f.input.fill('authentication');
  await expect(f.page.getByRole('status')).toBeVisible();
  await expect(f.page.getByRole('alert')).toBeVisible({timeout: 12000});
  await expect(f.input).toHaveValue('authentication');
  await expect(f.input).toBeEnabled();
  assert.deepEqual(await f.stats(), {fetches: 1, parses: 0, aborts: 1, credentials: ['same-origin']});
  f.release();
  assert.deepEqual(f.errors, []);
});
