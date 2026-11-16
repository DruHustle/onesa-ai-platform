"use client";
import { useState } from "react";
import {useRecordPage, RecordPageControls} from "../../lib/record-page";
import RequireSession from "../../components/require-session";
import FeatureShell from "../../components/feature-shell";
import { api, type AgentRunOut as Run } from "../../lib/api";

export default function Agents() {return <RequireSession destination="/agents" title="Bounded tools"><AgentsWorkspace /></RequireSession>;}
function AgentsWorkspace() {
  const page = useRecordPage<Run>("/agents/runs", "session", "run history");
  const {items: runs, setItems: setRuns, loading} = page;
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [goal, setGoal] = useState("");
  const [permission, setPermission] = useState(false);

  async function run(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !permission || !goal.trim()) return;
    setBusy(true);
    setError("");
    try {
      const result = await api("POST /agents/runs", {
        body: {
          goal,
          allowed_tools: ["text_stats"],
          steps: [{ tool: "text_stats", arguments: { text: goal } }],
        },
        signal: AbortSignal.timeout(15000),
      });
      setRuns((previous) => [result, ...previous.filter((item) => item.id !== result.id)]);
    } catch {
      setError("The run could not be confirmed. Check run history before submitting again; your text has been kept.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <FeatureShell title="Bounded tools">
      <p className="intro">
        Analyze text with a registered local tool. You choose the input and grant
        permission for each run. No model inference is needed for text statistics.
      </p>
      {error && <div className="error" role="alert">{error}</div>}
      <form onSubmit={run} className="feature-card" aria-busy={busy}>
        <label htmlFor="agent-goal">Text to analyze</label>
        <textarea id="agent-goal" name="goal" required maxLength={4000} value={goal}
          onChange={(event) => setGoal(event.target.value)} />
        <label className="checkbox">
          <input type="checkbox" name="permission" required checked={permission}
            onChange={(event) => setPermission(event.target.checked)} />
          Allow the text-statistics tool for this run
        </label>
        <button className="send" disabled={busy || !permission || !goal.trim()}>
          {busy ? "Running tool…" : "Run tool"}
        </button>
        <p className="intro">Local computation · Your private execution history</p>
      </form>
      <section aria-labelledby="run-history-title" aria-busy={loading}>
        <h2 id="run-history-title">Run history</h2>
        <RecordPageControls page={page} subject="run history" />
        {!loading && !page.error && runs.length === 0 && <div className="feature-card"><h3>Your results will appear here</h3><p>Enter text and grant permission to see its word and character counts.</p></div>}
        {runs.map((run) => (
          <article className="feature-card" key={run.id}>
            <h3>{run.goal}</h3>
            <p>Status: <span>{run.status}</span></p>
            {run.steps.map((step, index) => <div key={index}>
              {step.status === "completed" && step.tool === "text_stats" ? <dl className="tool-results">
                <div><dt>Words</dt><dd>{String(step.result.words ?? "—")}</dd></div>
                <div><dt>Characters</dt><dd>{String(step.result.characters ?? "—")}</dd></div>
              </dl> : step.status === "failed" ? <p>{step.error}</p>
                : <pre>{JSON.stringify(step.result, null, 2)}</pre>}
            </div>)}
          </article>
        ))}
      </section>
    </FeatureShell>
  );
}
