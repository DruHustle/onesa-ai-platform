"use client";
import { useRef, useState } from "react";
import {api, type EvidenceBundle, type ImportPreview, type InvestigationOut} from "../lib/api";

export default function IndustrialImport({locked, accept}: {
  locked: boolean; accept: (value: InvestigationOut) => void;
}) {
  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const identity = useRef<string | null>(null), pending = useRef(false);
  async function load(file?: File) {
    setBundle(null); setPreview(null); setError(""); identity.current = null;
    if (!file) return;
    if (file.size > 512 * 1024) { setError("Use a JSON bundle of at most 512 KiB."); return; }
    pending.current = true; setBusy(true);
    try { setBundle(JSON.parse(await file.text())); }
    catch { setError("Provide a UTF-8 JSON evidence bundle."); }
    finally { pending.current = false; setBusy(false); }
  }
  async function validate() {
    if (!bundle || pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try { setPreview(await api("POST /industrial/imports/preview", {body: bundle, signal: AbortSignal.timeout(10000)})); }
    catch { setError("Validation failed. Check the version, synthetic classification, asset, UTC timestamps, IANA timezone, units, IDs and reference hashes. No source was saved."); }
    finally { pending.current = false; setBusy(false); }
  }
  async function save() {
    if (!bundle || !preview || pending.current) return;
    pending.current = true; setBusy(true); setError(""); identity.current ||= crypto.randomUUID();
    try {
      accept(await api("POST /industrial/investigations", {body: {
        id: identity.current, scenario: "reference", asset_id: bundle.asset.id, start: bundle.window.start,
        end: bundle.window.end, source: bundle,
      }, signal: AbortSignal.timeout(15000)}));
    } catch { setError("Import could not be confirmed. Your validated source is kept here; retry with the same identity or check saved investigations."); }
    finally { pending.current = false; setBusy(false); }
  }
  return <section lang="en" className="feature-card" aria-labelledby="industrial-import-title" aria-busy={busy}>
    <h2 id="industrial-import-title">Import synthetic evidence</h2>
    <p>Read-only JSON adapter v1 · synthetic inputs only. Customer processing requires separate approval. This file adapter has no live machine connection.</p>
    <label>Versioned evidence bundle (.json, up to 512 KiB)
      <input type="file" accept=".json,application/json" disabled={locked || busy}
        onChange={event => void load(event.target.files?.[0])} />
    </label>
    {error && <p role="alert">{error}</p>}
    <button disabled={locked || busy || !bundle} onClick={validate}>Validate and preview import</button>
    {preview && bundle && <div>
      <p>{bundle.asset.name} · {bundle.asset.metadata_version} · {bundle.source_timezone}</p>
      <p>{bundle.window.start} → {bundle.window.end}</p>
      <p>Known downtime: {String(preview.facts.known_downtime_seconds)} seconds · completeness: {preview.facts.downtime_complete ? "complete in supplied events" : "lower bound"}. Cause not established.</p>
      <p>Missing evidence: {Array.isArray(preview.coverage.missing) ? preview.coverage.missing.join(", ") || "none identified by structural checks" : "review required"}.</p>
      <p>Validated source hash: <code style={{overflowWrap: "anywhere"}}>{preview.source_sha256}</code></p>
      <button disabled={locked || busy} onClick={save}>Save imported investigation</button>
    </div>}
  </section>;
}

export function IndustrialFactsTool({investigation, locked}: {investigation: InvestigationOut; locked: boolean}) {
  const [allowed, setAllowed] = useState(false), [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const pending = useRef(false);
  async function read() {
    if (!allowed || pending.current) return;
    pending.current = true; setBusy(true); setNotice("");
    try {
      const result = await api("POST /agents/runs", {body: {
        goal: "Read the selected investigation's saved deterministic facts",
        allowed_tools: ["industrial_facts"], steps: [{tool: "industrial_facts", arguments: {
          investigation_id: investigation.id, snapshot_sha256: investigation.payload.snapshot_sha256,
        }}],
      }, signal: AbortSignal.timeout(15000)});
      const step = result.steps[0];
      setNotice(step?.status === "completed"
        ? "The read-only tool returned the permitted saved facts for this exact evidence hash. Its result is in your tool-run history. No diagnosis or equipment action was performed."
        : "The source could not be read. Reopen it and verify access before retrying.");
    } catch { setNotice("The read could not be confirmed. Check tool-run history before retrying."); }
    finally {pending.current = false; setBusy(false);}
  }
  return <fieldset lang="en" disabled={locked || busy}>
    <legend>Read saved facts through a registered tool</legend>
    <label><input type="checkbox" checked={allowed} onChange={event => setAllowed(event.target.checked)} />Allow read-only access to this investigation for this run</label>
    <button disabled={!allowed || locked || busy} onClick={read}>Read saved investigation facts</button>
    {notice && <p role="status">{notice}</p>}
  </fieldset>;
}
