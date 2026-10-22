const { test } = require("node:test");
const assert = require("node:assert/strict");
const { mkdtempSync, writeFileSync, rmSync } = require("node:fs");
const { tmpdir } = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

test("account timeout is registered before browser/page fixtures start", () => {
  const app = path.resolve(__dirname, "../onesa-ai-platform-frontend/apps/chat");
  const temporary = mkdtempSync(path.join(tmpdir(), "onesa-test-registration-"));
  try {
    const reporter = path.join(temporary, "reporter.cjs");
    writeFileSync(reporter, `module.exports = class {
      onBegin(config, suite) {
        console.log(JSON.stringify(suite.allTests().map(test => ({
          project: test.parent.project().name, timeout: test.timeout
        }))));
      }
    };`);
    const result = spawnSync(process.execPath, [
      path.join(app, "node_modules/@playwright/test/cli.js"), "test",
      "tests/account.spec.ts", "--list", `--reporter=${reporter}`,
    ], { cwd: app, encoding: "utf8", timeout: 30_000 });
    assert.equal(result.status, 0, "Playwright registration must succeed");
    const registered = JSON.parse(result.stdout.trim());
    assert.deepEqual(registered, ["chromium", "firefox", "webkit"].map(project => ({
      project, timeout: 90_000,
    })), "the existing 90-second account budget must cover fixtures, not only the test body");
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});
