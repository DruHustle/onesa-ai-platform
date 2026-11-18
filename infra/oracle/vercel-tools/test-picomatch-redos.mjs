import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const picomatch = require('picomatch');
const micromatch = require('micromatch');
test('owner CLI uses scoped patched picomatch releases', () => {
 assert.equal(require('picomatch/package.json').version, '4.0.8-onesa.1');
 assert.equal(require('micromatch/node_modules/picomatch/package.json').version, '2.3.3-onesa.1');
 for (const pattern of ['+(*)', '+(*a)', '+(a*)', '*(a*|b)', '+(ab|abab)']) {
  assert.equal(picomatch.isMatch('a'.repeat(150)+'!', pattern), false, pattern);
 }
 assert.deepEqual(micromatch(['src/index.js','src/index.ts','src/x/a.js'], ['src/**/*.js']), ['src/index.js','src/x/a.js']);
 assert.equal(picomatch.isMatch('api/client.ts', '**/*.ts'), true);
});
