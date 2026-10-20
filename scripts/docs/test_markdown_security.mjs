import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';

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
