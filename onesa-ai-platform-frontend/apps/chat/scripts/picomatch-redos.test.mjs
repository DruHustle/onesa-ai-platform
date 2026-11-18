import test from "node:test";import assert from "node:assert/strict";import { createRequire } from "node:module";
const require=createRequire(import.meta.url);const picomatch=require("picomatch");
test("Onesa scoped fork explicitly blocks CVE-2026-112366 while preserving renderer glob matching",()=>{
 assert.equal(require("picomatch/package.json").version,"4.0.8-onesa.1");
 for(const pattern of ["+(*)","+(*a)","+(a*)","*(a*|b)","+(ab|abab)"]){
  assert.equal(picomatch.isMatch("a".repeat(150)+"!",pattern),false,pattern);
  assert.equal(picomatch.isMatch(pattern,pattern),true,pattern);
 }
 assert.equal(picomatch.isMatch("apps/chat/src/chat.tsx","apps/chat/src/**/*.tsx"),true);
 assert.equal(picomatch.isMatch("apps/chat/src/chat.js","apps/chat/src/**/*.tsx"),false);
 assert.equal(picomatch.isMatch("docs/.internal/secret.tsx","docs/**/*.tsx",{dot:true}),true);
 assert.equal(picomatch.isMatch("fff","*(f)"),true);
});
