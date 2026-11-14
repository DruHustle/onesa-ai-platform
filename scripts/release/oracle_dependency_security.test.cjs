'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {createRequire} = require('node:module');
const {setTimeout: delay} = require('node:timers/promises');
const {callableConsumer, compatiblePatterns, boundedPattern} = require('../glob_security.cjs');

const root = path.resolve(__dirname, '../..');
const cli = createRequire(path.join(root, 'infra/oracle/vercel-tools/package.json'));
const runtime = createRequire(path.join(root, 'infra/oracle/npm-runtime/package.json'));
const nft = createRequire(cli.resolve('@vercel/nft/package.json'));

function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'onesa-owner-dependency-'));
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  return directory;
}

function write(directory, file, content) {
  const target = path.join(directory, file);
  fs.mkdirSync(path.dirname(target), {recursive: true});
  fs.writeFileSync(target, content);
}

test('scoped legacy and modern owner consumers execute the exact reviewed matcher', async () => {
  assert.equal(cli('vercel/package.json').version, '65.2.0');
  assert.equal(cli('@ts-morph/common/package.json').version, '0.11.1');
  const legacy = callableConsumer(cli, '@ts-morph/common');
  const python = createRequire(cli.resolve('@vercel/python-analysis'));
  const glob = createRequire(nft.resolve('glob'));
  for (const consumer of [python, glob, runtime]) {
    assert.equal(consumer('minimatch/package.json').name, 'minimatch');
    assert.equal(consumer('minimatch/package.json').version, '11.0.1');
  }
  for (const entry of [legacy, python.resolve('minimatch'), glob.resolve('minimatch'), runtime.resolve('minimatch')]) {
    compatiblePatterns(entry);
    await boundedPattern(entry);
  }
});

test('actual ts-morph project selection retains exclusions and static Vercel config', () => {
  const {Project} = cli('ts-morph');
  const project = new Project({useInMemoryFileSystem: true});
  project.createSourceFile('/src/api.ts', 'export const config = {runtime: "nodejs", maxDuration: 12};');
  project.createSourceFile('/src/api.test.ts', 'export const testOnly = true;');
  project.createSourceFile('/other/ignored.ts', 'export const ignored = true;');
  assert.deepEqual(project.getSourceFiles(['/src/**/*.ts', '!/src/**/*.test.ts']).map(file => file.getFilePath()), ['/src/api.ts']);
  const {getConfig} = cli('@vercel/static-config');
  assert.deepEqual(getConfig(project, '/src/api.ts'), {runtime: 'nodejs', maxDuration: 12});
});

test('actual NFT traces dynamic file assets with fixed glob while excluding nested node_modules', async t => {
  const directory = fixture(t);
  write(directory, 'entry.cjs', 'const fs=require("fs"); const path=require("path"); module.exports=name=>fs.readFileSync(path.join(__dirname,"assets",name+".txt"),"utf8");');
  for (const file of ['assets/a.txt', 'assets/b.txt', 'assets/.hidden.txt', 'assets/node_modules/unowned.txt']) write(directory, file, 'synthetic');
  const {fileList} = await cli('@vercel/nft').nodeFileTrace([path.join(directory, 'entry.cjs')], {base: directory});
  for (const file of ['entry.cjs', 'assets/a.txt', 'assets/b.txt', 'assets/.hidden.txt']) assert.ok(fileList.has(file), `${file} must be traced`);
  assert.equal(fileList.has('assets/node_modules/unowned.txt'), false);
});

for (const [name, requireFrom] of [['Vercel NFT', nft], ['owner npm', runtime]]) {
  for (const mode of ['promise', 'stream']) {
    test(`GHSA-3g3m-2fjr-6pw4: ${name} ${mode} stops filesystem work after cancellation`, async t => {
      assert.equal(requireFrom('glob/package.json').version, '14.0.2');
      // Use the package's actual public entry, including any bundled matcher.
      const glob = requireFrom('glob');
      const directory = fixture(t);
      for (let a = 0; a < 4; a++) for (let b = 0; b < 4; b++) write(directory, `${a}/${b}/file.txt`, 'synthetic');
      const abort = new AbortController();
      const reason = new Error('synthetic traversal cancellation');
      let reads = 0;
      const trackedFs = {...fs, readdir(...args) {
        const callback = args.pop();
        reads++;
        fs.readdir(...args, (...result) => {
          if (reads === 1) abort.abort(reason);
          callback(...result);
        });
      }};
      const options = {cwd: directory, signal: abort.signal, fs: trackedFs};
      const result = mode === 'promise' ? glob.glob('**/*', options) : new Promise((resolve, reject) => {
        glob.globStream('**/*', options).on('data', () => {}).once('error', reject).once('end', resolve);
      });
      await assert.rejects(result, error => error === reason);
      const rejectedAt = reads;
      await delay(50);
      assert.equal(rejectedAt, 1);
      assert.equal(reads, rejectedAt, 'no background readdir after rejection');
    });
  }
}

test('npm workspace discovery preserves positive, negative, and re-included patterns', async t => {
  const directory = fixture(t);
  for (const name of ['api', 'web', 'excluded']) write(directory, `packages/${name}/package.json`, JSON.stringify({name: `fixture-${name}`, version: '1.0.0'}));
  const mapWorkspaces = runtime('@npmcli/map-workspaces');
  const selected = await mapWorkspaces({cwd: directory, pkg: {workspaces: ['packages/*', '!packages/excluded']}});
  assert.deepEqual([...selected.keys()].sort(), ['fixture-api', 'fixture-web']);
  const included = await mapWorkspaces({cwd: directory, pkg: {workspaces: ['packages/*', '!packages/excluded', 'packages/excluded']}});
  assert.deepEqual([...included.keys()].sort(), ['fixture-api', 'fixture-excluded', 'fixture-web']);
});

test('npm packlist keeps private and ignored files out while retaining explicit reinclusions', async t => {
  const directory = fixture(t);
  write(directory, 'package.json', JSON.stringify({name: 'onesa-synthetic-pack', version: '1.0.0'}));
  write(directory, '.npmignore', 'private/**\n*.log\n!keep.log\n');
  for (const file of ['index.js', 'private/secret.txt', 'debug.log', 'keep.log', '.git/config']) write(directory, file, 'synthetic only');
  const Arborist = runtime('@npmcli/arborist');
  const tree = await new Arborist({path: directory}).loadActual();
  const packlist = runtime('npm-packlist');
  const files = await packlist(tree);
  assert.ok(files.includes('package.json'));assert.ok(files.includes('index.js'));assert.ok(files.includes('keep.log'));
  for (const excluded of ['private/secret.txt', 'debug.log', '.git/config', '.npmignore']) assert.equal(files.includes(excluded), false, excluded);
});
