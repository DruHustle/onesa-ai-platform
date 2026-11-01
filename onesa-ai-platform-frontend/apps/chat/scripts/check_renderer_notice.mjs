import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const project = JSON.parse(await readFile(new URL("package.json", root)));
const lock = JSON.parse(await readFile(new URL("package-lock.json", root)));
const installed = JSON.parse(
  await readFile(new URL("node_modules/three/package.json", root)),
);
const entry = lock.packages["node_modules/three"];
assert.match(project.dependencies.three, /^\d+\.\d+\.\d+$/);
assert.equal(lock.packages[""].dependencies.three, project.dependencies.three);
assert.equal(entry.version, project.dependencies.three);
assert.equal(installed.name, "three");
assert.equal(installed.version, project.dependencies.three);
assert.equal(installed.license, "MIT");
assert.equal(entry.license, "MIT");
assert.equal(
  entry.resolved,
  "https://registry.npmjs.org/three/-/three-" + entry.version + ".tgz",
);
assert.match(entry.integrity, /^sha512-[A-Za-z0-9+/]{86}==$/);
assert.deepEqual(
  await readFile(new URL("public/licenses/three.txt", root)),
  await readFile(new URL("node_modules/three/LICENSE", root)),
  "The browser distribution must retain the exact installed Three.js MIT notice",
);
console.log("Pinned Three.js version, registry integrity and browser license notice verified.");
