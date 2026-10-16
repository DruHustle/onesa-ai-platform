const test = require("node:test"), assert = require("node:assert/strict");
const { safeFailureDiagnostics } = require("./ui_failure_diagnostics.cjs");

test("identifies the failed interaction without exception messages or assertion values", () => {
  const error = { name: "Error", message: "PRIVATE_SENTINEL", matcherResult: {
    name: "toBeFocused", expected: "PRIVATE_SENTINEL", actual: "PRIVATE_SENTINEL",
  } };
  const result = safeFailureDiagnostics(error, "focus_preserved");
  assert.deepEqual(result, { check: "focus_preserved", category: "assertion", matcher: "toBeFocused" });
  assert(!JSON.stringify(result).includes("PRIVATE_SENTINEL"));
});
test("timeouts retain only fixed category and trusted step", () => {
  assert.deepEqual(safeFailureDiagnostics({ name: "TimeoutError", message: "secret" }, "field_visible"),
    { check: "field_visible", category: "timeout", matcher: "not-recorded" });
});
test("foreign names, cycles and throwing getters cannot leak private values", () => {
  const cyclic = { name: "PRIVATE_SENTINEL", matcherResult: { name: "PRIVATE_SENTINEL" } };
  cyclic.self = cyclic;
  const throwing = { get matcherResult() { throw new Error("PRIVATE_SENTINEL"); } };
  for (const error of [null, cyclic, throwing, "PRIVATE_SENTINEL"]) {
    const result = safeFailureDiagnostics(error, "PRIVATE_SENTINEL");
    assert.deepEqual(result, { check: "not-recorded", category: "unavailable", matcher: "not-recorded" });
  }
});
