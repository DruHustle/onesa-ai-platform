'use strict';

const assert = require('node:assert/strict');
const {createRequire} = require('node:module');
const path = require('node:path');
const test = require('node:test');
const {callableConsumer, compatiblePatterns, boundedPattern} = require('../glob_security.cjs');

const contractRequire = createRequire(path.join(__dirname, 'package.json'));
const corePackage = contractRequire.resolve('@redocly/openapi-core/package.json');
const {readFileFromUrl} = contractRequire(path.join(path.dirname(corePackage), 'lib/utils.js'));

test('the actual Redocly consumer uses the provenance-bound fixed callable matcher', () => {
  assert.equal(contractRequire('@redocly/openapi-core/package.json').version, '1.34.20');
  callableConsumer(contractRequire, '@redocly/openapi-core');
});

test('the contract matcher retains ordinary glob behavior', () => {
  compatiblePatterns(callableConsumer(contractRequire, '@redocly/openapi-core'));
});

for (const [label, url, pattern, selected] of [
  ['protocol-less exact path', 'https://api.example.test/specs/openapi.yaml', 'api.example.test/specs/openapi.yaml', true],
  ['protocol-less path glob', 'https://api.example.test/specs/nested/openapi.yaml', 'api.example.test/specs/**', true],
  ['unrelated host', 'https://other.example.test/specs/openapi.yaml', 'api.example.test/specs/**', false],
  ['host suffix', 'https://api.example.test.other.invalid/specs/openapi.yaml', 'api.example.test/specs/**', false],
  ['unrelated path', 'https://api.example.test/private/openapi.yaml', 'api.example.test/specs/**', false],
  ['explicit matching protocol', 'https://api.example.test/specs/openapi.yaml', 'https://api.example.test/specs/**', true],
  ['explicit different protocol', 'http://api.example.test/specs/openapi.yaml', 'https://api.example.test/specs/**', false],
  ['host wildcard and extension alternatives', 'https://docs.example.test/specs/openapi.yaml', '*.example.test/specs/*.{yaml,json}', true],
  ['unselected extension', 'https://docs.example.test/specs/openapi.txt', '*.example.test/specs/*.{yaml,json}', false],
  ['negative extglob inclusion', 'https://api.example.test/specs/openapi.yaml', 'api.example.test/specs/!(*.private).yaml', true],
  ['negative extglob exclusion', 'https://api.example.test/specs/openapi.private.yaml', 'api.example.test/specs/!(*.private).yaml', false],
]) {
  test(`Redocly header selection: ${label}`, async () => {
    const requests = [];
    const response = await readFileFromUrl(url, {
      headers: [{matches: pattern, name: 'X-Onesa-Fixture', value: 'synthetic-only'}],
      customFetch: async (requestUrl, options) => {
        requests.push({url: requestUrl, headers: options.headers});
        return new Response('synthetic specification', {
          headers: {'content-type': 'application/yaml'},
        });
      },
    });
    assert.deepEqual(requests, [{
      url,
      headers: selected ? {'X-Onesa-Fixture': 'synthetic-only'} : {},
    }]);
    assert.deepEqual(response, {body: 'synthetic specification', mimeType: 'application/yaml'});
  });
}

test('the fixed matcher bounds adversarial pattern growth', {timeout: 5000}, async () => {
  await boundedPattern(callableConsumer(contractRequire, '@redocly/openapi-core'));
});
