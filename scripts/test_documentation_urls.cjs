const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { stripTypeScriptTypes } = require("node:module");
const source = fs.readFileSync(path.join(__dirname, "../onesa-ai-platform-frontend/apps/chat/src/lib/documentation.ts"), "utf8");
function urls(env) {
  const code = stripTypeScriptTypes(source).replace(/export const/g, "const");
  return vm.runInNewContext(code + ";documentationUrls", {process:{env}});
}
const production = urls({NODE_ENV:"production"});
assert.equal(production.public, "https://docs.onesa.eu");
assert.equal(production.internal, "");
const local = urls({NODE_ENV:"development"});
assert.equal(local.public, "http://localhost:3200");
assert.equal(local.internal, "http://localhost:3201");
const configured = urls({NODE_ENV:"production", NEXT_PUBLIC_ONESA_DOCUMENTATION_URL:"https://docs.onesa.eu", NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL:"https://approved-gateway.example.com"});
assert.equal(configured.internal, "https://approved-gateway.example.com");
assert.equal(configured.public, "https://docs.onesa.eu");
console.log("PASS: production public docs, absent unapproved engineering origin and explicit local/configured origins.");
