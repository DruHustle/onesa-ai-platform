"use client";

import {useEffect, useMemo, useRef, useState} from "react";
import Link from "next/link";
import RequireSession from "../../components/require-session";
import FeatureShell from "../../components/feature-shell";
import {call} from "../../lib/api";
import {useRecordPage, RecordPageControls} from "../../lib/record-page";
import styles from "./work.module.css";

type Tool = {
  name: string;
  effect: "local computation" | "read-only owned evidence";
  schema: Record<string, unknown>;
};
type Step =
  | {tool: string; status: "completed"; result: Record<string, unknown>}
  | {status: "failed"; error: string};
type Run = {
  id: string;
  goal: string;
  status: "running" | "completed" | "failed" | "cancelled";
  steps: Step[];
  created_at: string;
};
const label = (name: string) => name.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());

export default function Work() {
  return (
    <RequireSession destination="/work" title="Work">
      <WorkWorkspace />
    </RequireSession>
  );
}

function WorkWorkspace() {
  const history = useRecordPage<Run>("/agents/runs", "session", "work history");
  const [tools, setTools] = useState<Tool[]>([]);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [catalogError, setCatalogError] = useState("");
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const request = new AbortController();
    call("/agents/tools", "GET", undefined,
      AbortSignal.any([request.signal, AbortSignal.timeout(8000)]))
      .then(response => response.json())
      .then((data: {items: Tool[]}) => setTools(data.items))
      .catch(() => {
        if (!request.signal.aborted) setCatalogError("Tools are unavailable. Reload to retry.");
      });
    return () => {
      request.abort();
      controller.current?.abort();
    };
  }, []);

  const allowed = useMemo(
    () => permissions.filter(name => tools.some(tool => tool.name === name)),
    [permissions, tools],
  );
  const current = history.items.find(item => item.id === selectedRun) || null;
  async function execute(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !goal.trim() || !allowed.length) return;
    // This ID is generated before the network call. An ambiguous network failure
    // must never automatically resubmit a run with a new ID.
    const id = crypto.randomUUID();
    const signal = new AbortController();
    controller.current = signal;
    setBusy(true);
    setError("");
    setActiveRun(id);
    try {
      const response = await call("/agents/runs", "POST", {
        id, goal: goal.trim(), allowed_tools: allowed, steps: [],
      }, AbortSignal.any([signal.signal, AbortSignal.timeout(270000)]));
      const result: Run = await response.json();
      history.setItems(previous => [result, ...previous.filter(item => item.id !== result.id)]);
      setSelectedRun(result.id);
      history.reload();
    } catch {
      setError("The run could not be confirmed. Review saved history before retrying. No action was automatically replayed.");
      history.reload();
    } finally {
      controller.current = null;
      setBusy(false);
      setActiveRun(null);
    }
  }

  async function stop() {
    if (!activeRun) return;
    try {
      await call(`/agents/runs/${encodeURIComponent(activeRun)}/cancel`, "POST");
      controller.current?.abort();
      setError("The saved run was cancelled. Completed read-only steps may remain in history.");
      history.reload();
    } catch {
      // Planning may still be in progress, before the run record exists.
      controller.current?.abort();
      setError("Request disconnected. Cancellation was not confirmed: check run history.");
      history.reload();
    }
  }

  return (
    <FeatureShell title="Work" wide>
      <div className={styles.intro}>
        <div>
          <p className="eyebrow">AGENTIC WORKSPACE</p>
          <h2>Give Onesa AI a task, not just a question.</h2>
          <p>
            Onesa AI can plan and run up to eight registered tool steps.
            Choose the tools it may use before starting. Results are stored
            in your private execution history.
          </p>
        </div>
        <Link href="/plugins" className={styles.catalogLink}>Explore plugins</Link>
      </div>

      <div className={styles.columns}>
        <div className={styles.taskPanel}>
          <form onSubmit={execute} aria-busy={busy}>
            <label htmlFor="work-goal">What should Onesa AI work on?</label>
            <textarea id="work-goal" rows={5} maxLength={4000} required
              placeholder="For example: Analyze my document and summarize its key findings"
              value={goal} disabled={busy} onChange={event => setGoal(event.target.value)}/>
            <fieldset className={styles.permissions} disabled={busy}>
              <legend>Plugin permissions for this run</legend>
              <p>
                Only checked tools may be called. All currently available
                tools are local computation or read-only. Tools cannot install
                other plugins, access arbitrary websites, or make purchases.
              </p>
              {catalogError && <p role="alert" className="error">{catalogError}</p>}
              {!catalogError && !tools.length && <p role="status">Loading registered tools…</p>}
              {tools.map(tool => (
                <label className={styles.toolToggle} key={tool.name}>
                  <input type="checkbox" value={tool.name} checked={permissions.includes(tool.name)}
                    onChange={event => setPermissions(previous => event.target.checked
                      ? [...previous, tool.name] : previous.filter(name => name !== tool.name))}/>
                  <span>
                    <strong>{label(tool.name)}</strong>
                    <small>{tool.effect}</small>
                  </span>
                </label>
              ))}
            </fieldset>
            <p className={styles.notice}>
              Work runs use the configured inference provider. If inference is
              in mock mode, only the deterministic text-statistics plan runs;
              a mock result is not an AI-generated answer.
            </p>
            {error && <p className="error" role="alert">{error}</p>}
            <div className={styles.actions}>
              {busy ? (
                <button type="button" onClick={() => void stop()}>Stop run</button>
              ) : (
                <button className="send" disabled={!goal.trim() || !allowed.length || !tools.length}>
                  Approve tools &amp; run
                </button>
              )}
              <span role="status">{busy ? "Planning and executing your approved tools…" : ""}</span>
            </div>
          </form>
        </div>

        <section className={styles.history} aria-label="Saved Work and tool runs">
          <div className={styles.historyHeading}>
            <h2>Execution history</h2>
            <button type="button" onClick={history.reload} disabled={history.loading}>Refresh</button>
          </div>
          <RecordPageControls page={history} subject="work history"/>
          {!history.loading && !history.error && !history.items.length &&
            <p>No runs yet. Your completed tool evidence will appear here.</p>}
          <div className={styles.runList}>
            {history.items.map(run => (
              <button type="button" key={run.id}
                aria-pressed={selectedRun === run.id}
                className={selectedRun === run.id ? styles.activeRun : styles.run}
                onClick={() => setSelectedRun(run.id)}>
                <strong>{run.goal}</strong>
                <span>{run.status} · {new Date(run.created_at).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </section>
      </div>

      {current && (
        <section className={styles.results} aria-live="polite">
          <h2>Run result</h2>
          <p><strong>Goal:</strong> {current.goal}</p>
          <p><strong>Status:</strong> {current.status}</p>
          {current.steps.map((step, index) => (
            <article key={index} className={styles.step}>
              {step.status === "failed" ? (
                <>
                  <h3>Step {index + 1} · Unavailable</h3>
                  <p role="status">{step.error}</p>
                </>
              ) : (
                <>
                  <h3>{step.tool === "work_report" ? "AI work report" :
                    `Step ${index + 1} · ${label(step.tool)}`}</h3>
                  {step.tool === "work_report" ? (
                    <>
                      <p className={styles.notice}>Model-generated analysis of saved tool results.</p>
                      <p className={styles.report}>{String(step.result.text || "")}</p>
                    </>
                  ) : (
                    <pre>{JSON.stringify(step.result, null, 2)}</pre>
                  )}
                </>
              )}
            </article>
          ))}
        </section>
      )}
    </FeatureShell>
  );
}
