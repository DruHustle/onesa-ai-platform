/* Fixed diagnostic labels only: never serialize exceptions or assertion values. */
const checks = new Set([
  "navigate", "field_visible", "fill_draft", "focus_draft", "session_before",
  "change_system_preference", "observe_system_preference", "draft_preserved",
  "focus_preserved", "session_preserved", "no_appearance_api_requests",
  "no_stored_appearance", "restore_system_preference",
  "usability_sign_in_visible", "usability_submission_ready",
  "usability_sign_in_complete", "usability_navigation_url", "usability_field_editable",
]);
const matchers = new Set([
  "toBe", "toEqual", "toHaveValue", "toBeFocused", "toBeVisible", "toHaveCount",
  "toHaveURL", "toBeEnabled",
]);
function safeFailureDiagnostics(error, check) {
  let category = "unavailable", matcher = "not-recorded";
  try {
    if (error?.name === "TimeoutError") category = "timeout";
    const name = error?.matcherResult?.name;
    if (matchers.has(name)) { category = "assertion"; matcher = name; }
  } catch { /* Foreign getters must not escape or reveal exception contents. */ }
  return { check: checks.has(check) ? check : "not-recorded", category, matcher };
}
module.exports = { safeFailureDiagnostics };
