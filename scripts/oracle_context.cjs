/* Local Oracle probe metadata cannot authorize a production release. */
const fs = require("node:fs");
function privateJson(file) {
  const st = fs.lstatSync(file);
  if (!st.isFile() || (st.mode & 0o077) || st.uid !== process.getuid() || st.size > 16384)
    throw new Error("Private owner context required");
  return JSON.parse(fs.readFileSync(file, "utf8"));
}
function loadContext(file) {
  const c = privateJson(file);
  if (c.execution_context !== "owner-operated-oracle-staging" ||
      c.repository !== "DruHustle/onesa-ai-platform" ||
      !/^[a-f0-9]{40}$/.test(c.candidate_commit || "") ||
      !Number.isSafeInteger(c.ci_run_id) || c.ci_run_id <= 0 ||
      !/^prj_[A-Za-z0-9]+$/.test(c.project_id || "") ||
      !/^https:\/\/onesa-ai-platform-[a-z0-9-]+\.vercel\.app$/.test(c.frontend_origin || "") ||
      !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(c.qualification_id || ""))
    throw new Error("Invalid Oracle staging probe context");
  const f = privateJson(c.fixture_file), out = fs.lstatSync(c.output_dir);
  if (f.candidate_commit !== c.candidate_commit || f.run_id !== String(c.ci_run_id) ||
      f.project_id !== c.project_id || f.scope !== "approved-synthetic-staging" ||
      !Array.isArray(f.users) || f.users.length !== 2 || new Set(f.users.map(u => u.id)).size !== 2 ||
      f.users.some(u => !new RegExp("^release-audit-"+c.ci_run_id+"-[a-f0-9]{24}@example\\.com$").test(u.email || "")) ||
      !out.isDirectory() || (out.mode & 0o077) || out.uid !== process.getuid())
    throw new Error("Oracle fixture/output context mismatch");
  return c;
}
module.exports = { loadContext };
