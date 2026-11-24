import test from "node:test";import assert from "node:assert/strict";import { createRequire } from "node:module";
const require=createRequire(import.meta.url);
const picomatch=require("picomatch");
const micromatch=require("micromatch");
test("Docs scoped 2.x picomatch fork blocks repeated-extglob ReDoS and retains Docusaurus globs",()=>{
  assert.equal(require("picomatch/package.json").name,"@onesa/picomatch");
  assert.equal(require("picomatch/package.json").version,"2.3.3-onesa.1");
  for(const pattern of ["+(*)","+(*a)","+(a*)","*(a*|b)","+(ab|abab)"]){
    assert.equal(picomatch.isMatch("a".repeat(150)+"!",pattern),false,pattern);
    assert.equal(picomatch.isMatch(pattern,pattern),true,pattern);
  }
  for (const override of [{maxExtglobRecursion: false}, {maxExtglobRecursion: 999999}, {maxExtglobRecursion: Infinity}]) {
  assert.equal(picomatch.isMatch("a".repeat(150)+"!", "+(a*)", override), false, "security guard cannot be disabled");
  assert.equal(picomatch.isMatch("+(a*)", "+(a*)", override), true);
 }
 assert.equal(picomatch.isMatch("docs/internal/engineering.md","docs/**/*.md"),true);
  assert.equal(picomatch.isMatch("docs/internal/engineering.js","docs/**/*.md"),false);
  assert.deepEqual(micromatch(["a.md","a.ts","docs/b.md"],"**/*.md"),["a.md","docs/b.md"]);
});
