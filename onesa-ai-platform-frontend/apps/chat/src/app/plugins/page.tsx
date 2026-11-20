"use client";

import {useEffect, useState} from "react";
import Link from "next/link";
import FeatureShell from "../../components/feature-shell";
import RequireSession from "../../components/require-session";
import {call} from "../../lib/api";

type Tool = {
  name: string;
  schema: {properties?: Record<string, unknown>; required?: string[]};
  effect: "local computation" | "read-only owned evidence";
};
const family = (name: string) => {
  if (["text_stats", "arithmetic"].includes(name)) return "Utilities";
  if (name === "knowledge_search") return "Your Knowledge";
  if (name.startsWith("industrial_")) return "Industrial";
  if (name.startsWith("cybersecurity_")) return "Cybersecurity";
  return "Approved tools";
};
const title = (name: string) => name.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());

export default function Plugins() {
  return (
    <RequireSession title="Plugins" destination="/plugins">
      <PluginDirectory />
    </RequireSession>
  );
}

function PluginDirectory() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    call("/agents/tools", "GET", undefined,
      AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]))
      .then(response => response.json())
      .then((data: {items: Tool[]}) => {
        if (!controller.signal.aborted) setTools(data.items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("Unable to load the installed plugin catalog.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reload]);
  const groups = [...new Set(tools.map(tool => family(tool.name)))];
  return (
    <FeatureShell title="Plugins" wide>
      <p className="intro">
        Tools are the building blocks of Onesa Work. The catalog is served by
        the authenticated backend and only lists registered, available tools.
        Selecting a plugin here does not grant it access: you approve each
        tool separately for every Work run.
      </p>
      {error && <p className="error" role="alert">{error} <button type="button" onClick={() => {
        setError(""); setLoading(true); setReload(value => value + 1);
      }}>Retry</button></p>}
      {loading && <p role="status">Checking available plugins…</p>}
      {groups.map(group => (
        <section key={group} aria-label={group} className="feature-card">
          <h2>{group}</h2>
          <div className="suggestions">
            {tools.filter(tool => family(tool.name) === group).map(tool => (
              <article key={tool.name} className="feature-card" style={{flex: "1 1 230px"}}>
                <h3>{title(tool.name)}</h3>
                <p>{tool.effect === "local computation"
                  ? "Runs a bounded calculation inside Onesa."
                  : "Reads resources that your signed-in account is permitted to access."}</p>
                <p className="caption">Inputs: {Object.keys(tool.schema.properties || {}).join(", ") || "None"}</p>
                <p className="caption">Permission: {tool.effect} · Enabled on this server</p>
                <Link href="/work">Use in Work</Link>
              </article>
            ))}
          </div>
        </section>
      ))}
      {!loading && !error && !tools.length && <p>There are no registered tools for this account.</p>}
      <section className="feature-card" aria-label="External plugins">
        <h2>External app connections</h2>
        <p>
          Third-party services require a reviewed connector, authenticated
          authorization, scoped access, revocation, and an approval step for
          consequential changes. No arbitrary remote plugin endpoint is
          accepted from a model response or a browser form.
        </p>
        <p className="caption">
          External account connection and plugin installation are not enabled
          in this release. Onesa-owned Knowledge and approved local tools
          are available now.
        </p>
      </section>
    </FeatureShell>
  );
}
