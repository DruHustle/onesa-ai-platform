"use client";
import { useEffect, useState } from "react";
import FeatureShell from "../../components/feature-shell";
import { api, ApiError, type AgentRunOut as Run } from "../../lib/api";

export default function Agents() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [goal, setGoal] = useState("");
  const [permission, setPermission] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api("GET /agents/runs", { signal: AbortSignal.any([
      controller.signal, AbortSignal.timeout(8000),
    ]) })
      .then((result) => {
        if (!controller.signal.aborted) setRuns((previous) => [
          ...previous.filter((run) => !result.items.some((item) => item.id === run.id)),
          ...result.items,
        ]);
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) setHistoryError(
          failure instanceof ApiError && failure.status === 401
            ? "Sign in to view your tool runs."
            : "Run history is unavailable. Your text is kept here; retry when the connection is restored.",
        );
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [attempt]);

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
        <label>
          Text to analyze
          <textarea name="goal" required maxLength={4000} value={goal}
            onChange={(event) => setGoal(event.target.value)} />
        </label>
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
        {loading && <p role="status">Loading run history…</p>}
        {historyError && <div className="feature-card">
          <p role="alert">{historyError}</p>
          <button type="button" disabled={loading} onClick={() => {
            setHistoryError(""); setLoading(true); setAttempt((value) => value + 1);
          }}>Retry history</button>
        </div>}
        {!loading && !historyError && runs.length === 0 && <div className="feature-card">
          <h3>Your results will appear here</h3>
          <p>Enter text and grant permission to see its word and character counts.</p>
        </div>}
        {runs.map((run) => (
          <article className="feature-card" key={run.id}>
            <h3>{run.goal}</h3>
            <p>Status: {run.status}</p>
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
