"use client";
import { useEffect, useState } from "react";
import FeatureShell from "../../components/feature-shell";
import { call } from "../../lib/api";
type Run = {
  id: string;
  goal: string;
  status: string;
  steps: { tool?: string; status: string; result?: unknown; error?: string }[];
};
export default function Agents() {
  const [runs, setRuns] = useState<Run[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    call("/agents/runs")
      .then((r) => r.json())
      .then((r) => setRuns(r.items))
      .catch((e) => setError(e.message));
  }, []);
  async function run(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await call("/agents/runs", "POST", {
        goal: form.get("goal"),
        allowed_tools: form.get("permission") ? ["text_stats"] : [],
      });
      const r = await call("/agents/runs");
      setRuns((await r.json()).items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <FeatureShell title="Bounded tools">
      <p className="intro">
        Run a registered local text-statistics tool. Each run requires explicit
        permission and keeps an execution record.
      </p>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      <form onSubmit={run} className="feature-card">
        <label>
          Text to analyze
          <textarea name="goal" required maxLength={4000} />
        </label>
        <label className="checkbox">
          <input type="checkbox" name="permission" required />
          Allow the text-statistics tool for this run
        </label>
        <button className="send" disabled={busy}>
          Run tool
        </button>
      </form>
      {runs.map((r) => (
        <article className="feature-card" key={r.id}>
          <strong>{r.goal}</strong>
          <p>{r.status}</p>
          <pre>{JSON.stringify(r.steps, null, 2)}</pre>
        </article>
      ))}
    </FeatureShell>
  );
}
