'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {createRequire} = require('node:module');
const {boundedPattern, compatiblePatterns} = require('./glob_security.cjs');

const root = path.resolve(__dirname, '..');
const chat = createRequire(path.join(root, 'onesa-ai-platform-frontend/apps/chat/package.json'));

function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'onesa-lint-globs-'));
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  return directory;
}

function write(directory, file, content) {
  const target = path.join(directory, file);
  fs.mkdirSync(path.dirname(target), {recursive: true});
  fs.writeFileSync(target, content);
  return target;
}

function packageMetadata(name) {
  const modules = path.join(root, 'onesa-ai-platform-frontend/apps/chat/node_modules');
  let directory = path.dirname(chat.resolve(name));
  while (directory.startsWith(modules + path.sep)) {
    const file = path.join(directory, 'package.json');
    if (fs.existsSync(file)) {
      const metadata = JSON.parse(fs.readFileSync(file, 'utf8'));
      if (metadata.name === name) return metadata;
    }
    directory = path.dirname(directory);
  }
  throw new Error(`Installed package metadata missing: ${name}`);
}

test('all three pinned modern lint consumers resolve the fixed bounded matcher', async () => {
  for (const [parent, version] of [['eslint', '10.12.0'], ['@eslint/config-array', '0.23.5'], ['@typescript-eslint/typescript-estree', '8.71.1']]) {
    const consumer = createRequire(chat.resolve(parent));
    assert.equal(packageMetadata(parent).version, version);
    assert.equal(consumer('minimatch/package.json').version, '11.0.1');
    const entry = consumer.resolve('minimatch');
    compatiblePatterns(entry);
    await boundedPattern(entry);
  }
});

test('real ESLint preserves file selection, ignored directories, negations and fatal diagnostics', async t => {
  const directory = fixture(t);
  write(directory, 'src/good.js', 'const value = 1; export {value};');
  write(directory, 'src/bad.js', 'unknownValue();');
  write(directory, 'src/fatal.cjs', 'const = ;');
  write(directory, 'src/.dot.js', 'dotUndefined();');
  write(directory, 'src/skipped.test.js', 'const = ;');
  write(directory, 'generated/ignored.js', 'const = ;');
  write(directory, 'generated/reviewed.js', 'reviewedUndefined();');
  const {ESLint} = chat('eslint');
  const eslint = new ESLint({
    cwd: directory,
    overrideConfigFile: true,
    overrideConfig: [
      {ignores: ['generated/**/*', '!generated/reviewed.js', '**/*.test.js']},
      {files: ['**/*.{js,cjs}'], rules: {'no-undef': 'error'}},
    ],
  });
  const results = await eslint.lintFiles(['**/*.{js,cjs}']);
  const byName = new Map(results.map(result => [path.relative(directory, result.filePath), result]));
  assert.deepEqual([...byName.keys()].sort(), ['generated/reviewed.js', 'src/.dot.js', 'src/bad.js', 'src/fatal.cjs', 'src/good.js']);
  assert.equal(byName.get('src/good.js').errorCount, 0);
  for (const name of ['generated/reviewed.js', 'src/.dot.js', 'src/bad.js']) {
    assert.equal(byName.get(name).errorCount, 1, name);
    assert.equal(byName.get(name).messages[0].ruleId, 'no-undef');
  }
  assert.equal(byName.get('src/fatal.cjs').fatalErrorCount, 1);
  await assert.rejects(eslint.lintFiles(['missing/**/*.js']), /No files matching/);
});

test('actual TypeScript project service accepts only its explicit default-project glob', t => {
  const directory = fixture(t);
  write(directory, 'tsconfig.json', JSON.stringify({compilerOptions: {strict: true}, include: ['src/**/*.ts']}));
  write(directory, 'src/inside.ts', 'export const inside = 1;');
  const allowed = write(directory, 'allowed.ts', 'export const value: number = 1;');
  const denied = write(directory, 'denied.ts', 'export const value: number = 2;');
  const parser = chat('@typescript-eslint/typescript-estree');
  t.after(() => parser.clearCaches());
  const options = {tsconfigRootDir: directory, projectService: {allowDefaultProject: ['allowed.ts']}};
  const result = parser.parseAndGenerateServices(fs.readFileSync(allowed, 'utf8'), {...options, filePath: allowed});
  assert.ok(result.services.program);
  assert.throws(() => parser.parseAndGenerateServices(fs.readFileSync(denied, 'utf8'), {...options, filePath: denied}), /not found by the project service|not included|allowDefaultProject/i);
});
