/* Local Oracle probe metadata cannot authorize a production release. */
const fs = require("node:fs");
const path = require("node:path");
function writeReceipt(file, value) {
  const raw = JSON.stringify(value, null, 2);
  const directory = path.dirname(file), parent = fs.lstatSync(directory);
  if (!parent.isDirectory() || parent.isSymbolicLink() ||
      parent.uid !== process.getuid() || (parent.mode & 0o022))
    throw new Error("Owned receipt directory required");
  const fd = fs.openSync(file,
    fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW,
    0o600);
  try { fs.writeFileSync(fd, raw); fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
  const dir = fs.openSync(directory, fs.constants.O_RDONLY);
  try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); }
}
function privateJson(file) {
  const st = fs.lstatSync(file);
  if (!st.isFile() || (st.mode & 0o077) || st.uid !== process.getuid() || st.size > 16384)
    throw new Error("Private owner context required");
  return JSON.parse(fs.readFileSync(file, "utf8"));
}
function loadContext(file) {
  const c = privateJson(file);
  if (c.repository === "DruHustle/onesa-ug") {
    const s = c.source_binding;
    const keys = ["schema_version", "repository", "repository_id", "product", "source_path",
      "candidate_commit", "source_tree", "product_source_tree", "branch"];
    if (!s || typeof s !== "object" || Array.isArray(s) ||
        Object.keys(s).length !== keys.length || keys.some(k => !Object.hasOwn(s, k)) ||
        s.schema_version !== 2 || s.repository !== c.repository || s.repository_id !== 1444746154 ||
        s.product !== "platform" || s.source_path !== "onesa-ai-platform" || s.branch !== "main" ||
        ["candidate_commit", "source_tree", "product_source_tree"].some(k =>
          typeof s[k] !== "string" || !/^[a-f0-9]{40}$/.test(s[k])) ||
        s.candidate_commit !== c.candidate_commit)
      throw new Error("Oracle canonical source context mismatch");
  } else if (c.repository !== "DruHustle/onesa-ai-platform" || Object.hasOwn(c, "source_binding")) {
    throw new Error("Invalid Oracle source context");
  }
  if (c.execution_context !== "owner-operated-oracle-staging" ||
      !/^[a-f0-9]{40}$/.test(c.candidate_commit || "") ||
      !Number.isSafeInteger(c.ci_run_id) || c.ci_run_id <= 0 ||
      !/^prj_[A-Za-z0-9]+$/.test(c.project_id || "") ||
      !/^https:\/\/onesa-ai-platform-[a-z0-9-]+\.vercel\.app$/.test(c.frontend_origin || "") ||
      !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(c.qualification_id || ""))
    throw new Error("Invalid Oracle staging probe context");
  const f = privateJson(c.fixture_file), out = fs.lstatSync(c.output_dir);
  if (c.identity) require('./release/oracle_ai_identity_context.cjs').validateContext(c, f.users);
  if (f.candidate_commit !== c.candidate_commit || f.run_id !== String(c.ci_run_id) ||
      f.project_id !== c.project_id || f.scope !== "approved-synthetic-staging" ||
      !Array.isArray(f.users) || f.users.length !== 2 || new Set(f.users.map(u => u.id)).size !== 2 ||
      (!c.identity && f.users.some(u => !new RegExp("^release-audit-"+c.ci_run_id+"-[a-f0-9]{24}@example\\.com$").test(u.email || ""))) ||
      !out.isDirectory() || (out.mode & 0o077) || out.uid !== process.getuid())
    throw new Error("Oracle fixture/output context mismatch");
  return c;
}
module.exports = { loadContext, writeReceipt };
