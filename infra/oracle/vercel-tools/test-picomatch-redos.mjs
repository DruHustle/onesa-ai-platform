import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const require = createRequire(import.meta.url);
const root = dirname(fileURLToPath(import.meta.url));
const releases = [
  { directory: "onesa-picomatch-redos-4.0.8-onesa.1", version: "4.0.8-onesa.1",
    parseBlob: "526b223084caa8bc76ab5706d3257b90af0cf762" },
  { directory: "onesa-picomatch-redos-2.3.3-onesa.1", version: "2.3.3-onesa.1",
    parseBlob: "aa99da7ba6195cd0e9b991517bbaaa41ae4b6184" }
];

function gitBlobSha(data) {
  return createHash("sha1").update("blob " + data.length + "\0").update(data).digest("hex");
}

for (const release of releases) {
  test(release.directory + " has the reviewed patched source and safe actual glob semantics", () => {
    const dir = join(root, "vendor", release.directory);
    const pkg = require(join(dir, "package.json"));
    assert.equal(pkg.name, "@onesa/picomatch");
    assert.equal(pkg.version, release.version);
    assert.equal(gitBlobSha(readFileSync(join(dir, "lib/parse.js"))), release.parseBlob);
    const picomatch = require(dir);
    for (const pattern of ["+(*)", "+(*a)", "+(a*)", "*(a*|b)", "+(ab|abab)"]) {
      assert.equal(picomatch.isMatch("a".repeat(150) + "!", pattern), false, pattern);
      assert.equal(picomatch.isMatch(pattern, pattern), true, pattern);
    }
    assert.equal(picomatch.isMatch("src/nested/build.js", "**/*.js"), true);
    assert.equal(picomatch.isMatch("src/nested/build.ts", "**/*.js"), false);
  });
}
