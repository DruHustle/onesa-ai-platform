'use strict';
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const {Worker} = require('node:worker_threads');

const root = path.resolve(__dirname, '..');
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function callableConsumer(requireFrom, parent) {
  const consumer = createRequire(requireFrom.resolve(`${parent}/package.json`));
  const entry = consumer.resolve('minimatch');
  const directory = path.dirname(consumer.resolve('minimatch/package.json'));
  const metadata = consumer('minimatch/package.json');
  assert.equal(metadata.name, '@onesa/minimatch-callable');
  const record = require('../packages/security/provenance.json')['minimatch-callable'];
  for (const [file, expected] of Object.entries(record.shipped_files)) {
    assert.equal(digest(fs.readFileSync(path.join(directory, file))), expected, `${parent}: ${file}`);
  }
  for (const archive of [record.archive, ...(record.additional_archives || [])]) {
    assert.equal(digest(fs.readFileSync(path.join(root, archive))), record.archive_sha256);
  }
  const adapter = createRequire(entry);
  assert.equal(adapter('minimatch-fixed/package.json').version, '11.0.1');
  assert.equal(consumer('minimatch'), adapter('minimatch-fixed').minimatch);
  return entry;
}

function compatiblePatterns(entry) {
  const exported = require(entry);
  const match = typeof exported === 'function' ? exported : exported.minimatch;
  for (const [file, pattern, options, expected] of [
    ['docs/api/guide.md', 'docs/**/*.{md,mdx}', {}, true],
    ['docs/api/guide.txt', 'docs/**/*.{md,mdx}', {}, false],
    ['src/a.ts', 'src/!(*.test).ts', {}, true],
    ['src/a.test.ts', 'src/!(*.test).ts', {}, false],
    ['docs/.private', 'docs/*', {}, false],
    ['docs/.private', 'docs/*', {dot: true}, true],
    ['docs/guide.md', '*.md', {matchBase: true}, true],
    ['docs/guide[1].md', 'docs/guide\\[1\\].md', {}, true],
    ['docs/guide.md', '!**/*.txt', {}, true],
  ]) assert.equal(match(file, pattern, options), expected, `${file}: ${pattern}`);
}

async function boundedPattern(entry) {
  // Run the adversarial pattern in a bounded worker so a regression cannot hang
  // the test runner or consume unbounded memory before reporting the failure.
  const worker = new Worker(`
    const {parentPort, workerData} = require('node:worker_threads');
    const exported = require(workerData);
    const pattern = Array.from({length: 18}, (_, i) => '**/../segment' + i + '/leaf' + i).join('/');
    const matcher = new exported.Minimatch(pattern, {optimizationLevel: 2, braceExpandMax: 64});
    parentPort.postMessage({parts: matcher.globParts.length, normal: matcher.match('ordinary/file')});
  `, {eval: true, workerData: entry, resourceLimits: {maxOldGenerationSizeMb: 64}});
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Matcher exceeded its bounded worker deadline')), 3000);
      worker.once('error', error => { clearTimeout(timer); reject(error); });
      worker.once('message', result => {
        clearTimeout(timer);
        try {
          assert.ok(result.parts <= 64, 'globparts amplification respects the upstream expansion ceiling');
          assert.equal(result.normal, false);
          resolve();
        } catch (error) { reject(error); }
      });
    });
  } finally { await worker.terminate(); }
}

module.exports = {callableConsumer, compatiblePatterns, boundedPattern};
