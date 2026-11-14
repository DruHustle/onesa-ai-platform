import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import sourceComments from './markdown-comments.mjs';

const require = createRequire(new URL('../../onesa-ai-platform-frontend/apps/docs/package.json', import.meta.url));
const parser = require.resolve('markdown-it');

// GHSA-vfgh-jcmw-g37q: unterminated inline HTML must not repeatedly scan
// overlapping suffixes. Bound the child process so a regression cannot hang CI.
for (const [name, opener] of Object.entries({comment: '<!--', processing: '<?x', declaration: '<!A', cdata: '<![CDATA['})) {
  test(`HTML-enabled Markdown handles repeated unterminated ${name} within the execution bound`, () => {
    const program = `
      const assert = require('node:assert/strict');
      const MarkdownIt = require(process.argv[1]);
      const source = 'x ' + process.argv[2].repeat(64000);
      const html = new MarkdownIt({html: true}).render(source);
      assert.ok(html.startsWith('<p>x '));
      assert.ok(html.length >= source.length);
    `;
    execFileSync(process.execPath, ['-e', program, parser, opener], {timeout: 5000, maxBuffer: 1024, stdio: 'pipe'});
  });
}

test('normal documentation links, headings and HTML policy remain intact', () => {
  const MarkdownIt = require('markdown-it');
  const source = '# Guide\n\n[Onesa](https://onesa.eu/)\n\n<strong>Example</strong>\n';
  const enabled = new MarkdownIt({html: true}).render(source);
  const disabled = new MarkdownIt({html: false}).render(source);
  assert.ok(enabled.includes('<h1>Guide</h1>'));
  assert.ok(enabled.includes('<a href="https://onesa.eu/">Onesa</a>'));
  assert.ok(enabled.includes('<strong>Example</strong>'));
  assert.ok(disabled.includes('&lt;strong&gt;Example&lt;/strong&gt;'));
});

test('manuals hide closed source comments while preserving headings and ordinary HTML escaping', () => {
  const MarkdownIt = require('markdown-it');
  const md = new MarkdownIt({html: false}).use(sourceComments);
  const html = md.render('# Guide\n\n<!-- private annotation\n\n# Not a heading\n-->\n\nPublic <!-- annotation --> prose.\n\n<strong>Example</strong>\n');
  assert.ok(html.includes('<h1>Guide</h1>'));
  assert.ok(html.includes('Public  prose.'));
  assert.ok(html.includes('&lt;strong&gt;Example&lt;/strong&gt;'));
  assert.ok(!html.includes('annotation'));
  assert.ok(!html.includes('Not a heading'));
});

test('comment-like code, escaped text, following text and unterminated input remain visible', () => {
  const MarkdownIt = require('markdown-it');
  const md = new MarkdownIt({html: false}).use(sourceComments);
  for (const source of ['`<!-- code -->`', '```html\n<!-- code -->\n```', '    <!-- code -->', '\\<!-- escaped -->']) {
    assert.ok(md.render(source).includes('&lt;!--'), source);
  }
  assert.ok(md.render('<!-- hidden -->Visible').includes('Visible'));
  assert.ok(md.render('<!-- unfinished').includes('&lt;!-- unfinished'));
  // Failed search bounds must belong to an individual parse, not the shared parser.
  assert.equal(md.render('<!-- closed -->'), '');
  assert.ok(md.render('> <!-- hidden -->\n>\n> Visible').includes('Visible'));
  assert.ok(!md.render('> <!-- hidden -->').includes('hidden'));
});

test('manual comment handling bounds repeated unterminated block and inline searches', () => {
  const plugin = new URL('./markdown-comments.mjs', import.meta.url).href;
  for (const source of ['x ' + '<!--'.repeat(64000), '<!--\n\n'.repeat(64000), '<!--\n\n'.repeat(64000) + '-->following text', '<!--\n\n'.repeat(64000) + '-->' + ' '.repeat(64000) + 'text']) {
    const program = `
      import {createRequire} from 'node:module';
      import sourceComments from ${JSON.stringify(plugin)};
      const require = createRequire(import.meta.url);
      const MarkdownIt = require(process.argv[1]);
      const html = new MarkdownIt({html: false}).use(sourceComments).render(process.argv[2]);
      if (!html.includes('&lt;!--')) throw new Error('Unterminated comments disappeared');
    `;
    // Pass the sizeable fixture through stdin rather than the platform argv limit.
    const stdinProgram = program.replace('process.argv[2]', "require('node:fs').readFileSync(0, 'utf8')");
    execFileSync(process.execPath, ['--input-type=module', '-e', stdinProgram, parser], {input: source, timeout: 5000, maxBuffer: 1024, stdio: ['pipe', 'pipe', 'pipe']});
  }
});


test('manual contents labels use visible heading text without comments or Markdown markers', () => {
  const MarkdownIt = require('markdown-it');
  const md = new MarkdownIt({html: false}).use(sourceComments);
  const heading = md.parse('# **Guide** <!-- internal note --> and `code`', {}).find(t => t.type === 'inline');
  assert.equal(md.renderer.renderInlineAsText(heading.children, md.options, {}), 'Guide  and code');
  assert.ok(!md.render('# **Guide** <!-- internal note --> and `code`').includes('internal note'));
});
