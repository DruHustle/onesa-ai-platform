"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import RequireSession from "../../../components/require-session";
import FeatureShell from "../../../components/feature-shell";
import { call, csrf } from "../../../lib/api";
import {
  security,
  eventExample,
  type Asset,
  type Finding,
  type SecurityEvent,
  type Workspace,
  type Readiness,
  type CaseDetail,
  type Action,
  type Inventory,
  type ReportMetadata,
} from "../../../lib/cybersecurity";
import styles from "./security.module.css";

const views = [
  "Overview",
  "Assets",
  "Events",
  "Findings",
  "Investigations",
  "Sources",
] as const;
type View = (typeof views)[number];
const date = (value: string | null) =>
  value
    ? new Date(value).toLocaleString(undefined, { timeZoneName: "short" })
    : "Unknown";
const json = (value: unknown) => JSON.stringify(value, null, 2);
function Fields({ children }: { children: React.ReactNode }) {
  return <div className={styles.panel}>{children}</div>;
}
function Badge({ children }: { children: React.ReactNode }) {
  return <span className={styles.badge}>{children}</span>;
}
function WorkspacePage() {
  const params = useSearchParams();
  const requestedFinding = params.get("finding");
  const [data, setData] = useState<Workspace | null>(null),
    [ready, setReady] = useState<Readiness | null>(null),
    [view, setView] = useState<View>(() =>
      views.includes(params.get("view") as View)
        ? (params.get("view") as View)
        : "Overview",
    ),
    [mode, setMode] = useState(() =>
      ["live", "simulated", "replay"].includes(params.get("mode") || "")
        ? params.get("mode")!
        : "live",
    ),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [loaded, setLoaded] = useState(false);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null),
    [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null),
    [selectedAsset, setSelectedAsset] = useState<Asset | null>(null),
    [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null),
    [sourceId, setSourceId] = useState(""),
    [token, setToken] = useState(""),
    [input, setInput] = useState(""),
    [search, setSearch] = useState(""),
    [searchEvents, setSearchEvents] = useState<SecurityEvent[] | null>(null),
    [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [decisionSnapshot, setDecisionSnapshot] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [assetReports, setAssetReports] = useState<ReportMetadata[]>([]),
    [inventory, setInventory] = useState<Inventory | null>(null),
    [configurationDetail, setConfigurationDetail] = useState<Record<
      string,
      unknown
    > | null>(null);
  const [eventCursor, setEventCursor] = useState<string | undefined>(undefined),
    [appliedSearch, setAppliedSearch] = useState(""),
    [exportNext, setExportNext] = useState<Record<string, string>>({});
  const pending = useRef(false),
    inspector = useRef<HTMLElement | null>(null);
  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      const result = await security<Workspace>(
        `/workspace?mode=${mode}`,
        "GET",
        undefined,
        signal,
      );
      if (!signal?.aborted) {
        setData(result);
        setSelectedFinding((current) =>
          current && result.findings.some((item) => item.id === current.id)
            ? current
            : null,
        );
        setCaseDetail((current) =>
          current &&
          result.investigations.some(
            (item) => item.id === current.investigation.id,
          )
            ? current
            : null,
        );
      }
    },
    [mode],
  );
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      security<Readiness>("/readiness", "GET", undefined, controller.signal),
      security<Workspace>(
        `/workspace?mode=${mode}`,
        "GET",
        undefined,
        controller.signal,
      ),
    ])
      .then(([r, d]) => {
        if (!controller.signal.aborted) {
          setReady(r);
          setData(d);
          const linked = d.findings.find((f) => f.id === requestedFinding);
          if (linked) {
            setSelectedFinding(linked);
            setSelectedAsset(
              d.assets.find((a) => a.id === linked.asset_id) || null,
            );
          }
          setError("");
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError((e as Error).message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoaded(true);
      });
    return () => controller.abort();
  }, [mode, requestedFinding]);
  function choose(next: View) {
    setView(next);
    const url = new URL(window.location.href);
    url.searchParams.set("view", next);
    url.searchParams.set("mode", mode);
    window.history.replaceState(null, "", url);
  }
  function changeMode(next: string) {
    setMode(next);
    setEventCursor(undefined);
    setAppliedSearch("");
    setExportNext({});
    setCaseDetail(null);
    setSelectedFinding(null);
    setSelectedEvent(null);
    setSearchEvents(null);
    setSummary(null);
    const url = new URL(window.location.href);
    url.searchParams.set("mode", next);
    window.history.replaceState(null, "", url);
  }
  async function run(action: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  function submitted(
    event: React.FormEvent<HTMLFormElement>,
    action: (values: FormData) => Promise<void>,
  ) {
    event.preventDefault();
    const form = event.currentTarget,
      values = new FormData(form);
    void run(async () => {
      await action(values);
      await refresh();
      setNotice("Saved to this security workspace.");
    });
  }
  function focusInspector() {
    window.setTimeout(() => inspector.current?.focus(), 0);
  }
  async function downloadEvidence(format: string, before?: string) {
    await run(async () => {
      const response = await call(
        `/cybersecurity/export?mode=${mode}&format=${format}${sourceId ? `&source_id=${sourceId}` : ""}${before ? `&before=${before}` : ""}`,
      );
      const next = response.headers.get("X-Next-Cursor") || "";
      setExportNext((current) => ({ ...current, [format]: next }));
      const url = URL.createObjectURL(await response.blob()),
        link = document.createElement("a");
      link.href = url;
      link.download = `onesa-security.${format}`;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice(
        `Exported ${response.headers.get("X-Exported-Events") || "0"} authorized events.${next ? " Another page is available." : " This export scope has no earlier page."}`,
      );
    });
  }
  async function openAsset(value: Asset) {
    await run(async () => {
      const detail = await security<{
        asset: Asset;
        reports: ReportMetadata[];
      }>(`/assets/${value.id}`);
      setSelectedAsset(detail.asset);
      setAssetReports(detail.reports);
      setInventory(null);
      choose("Assets");
      focusInspector();
    });
  }
  async function openFinding(value: Finding) {
    await run(async () => {
      const result = await security<{ finding: Finding; asset: Asset | null }>(
        `/findings/${value.id}`,
      );
      setSelectedFinding(result.finding);
      setSelectedAsset(result.asset);
      setAssetReports([]);
      setInventory(null);
      choose("Findings");
      focusInspector();
    });
  }
  async function openCase(id: string) {
    await run(async () => {
      setCaseDetail(await security<CaseDetail>(`/investigations/${id}`));
      setDecisionSnapshot(null);
      setSummary(null);
      choose("Investigations");
      focusInspector();
    });
  }
  async function importFile(file: File | undefined) {
    if (!file) return;
    if (file.size > 1048576) {
      setError("Evidence batches must be at most 1 MiB.");
      return;
    }
    setInput(await file.text());
  }
  const selectedSource = data?.sources.find((s) => s.id === sourceId),
    sourceName = (id: string) =>
      data?.sources.find((s) => s.id === id)?.name || "Authorized source",
    assetName = (id: string | null) =>
      data?.assets.find((a) => a.id === id)?.name ||
      "Source scope; no equipment mapping";
  const shownEvents = searchEvents || data?.events || [];
  const nextEvents =
    eventCursor === undefined
      ? data?.events.length === 100
        ? data.events[99].id
        : null
      : eventCursor || null;
  return (
    <FeatureShell title="Cybersecurity" wide>
      <p className={styles.intro}>
        Review security evidence, understand affected assets, and record
        investigation decisions. Findings explain observed conditions; they do
        not establish compromise or certification.
      </p>
      <div className={styles.toolbar}>
        <div className={styles.badges}>
          <Badge>Read-only monitoring</Badge>
          <Badge>
            {ready?.operator ? "Configured operator access" : "Owned workspace"}
          </Badge>
          <Badge>Human decisions</Badge>
        </div>
        <label>
          Evidence mode
          <select
            aria-label="Evidence mode"
            value={mode}
            onChange={(e) => changeMode(e.target.value)}
            disabled={busy}
          >
            <option value="live">Live / declared observations</option>
            <option value="simulated">Explicitly simulated</option>
            <option value="replay">Separate replay</option>
          </select>
        </label>
        <button
          disabled={busy || !data}
          onClick={() => void run(() => refresh())}
        >
          Refresh evidence
        </button>
        <button
          disabled={busy || !data}
          onClick={() =>
            void run(async () => {
              await security("/assess", "POST");
              await refresh();
              setNotice(
                "Assessed configured delivery intervals and retained certificate metadata; coverage loss is not an attack finding.",
              );
            })
          }
        >
          Assess source freshness
        </button>
        {ready?.demo_enabled && mode !== "live" && (
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await security("/demo", "POST", {
                  mode,
                  run_id: crypto.randomUUID(),
                });
                await refresh();
                setNotice(
                  `Added explicitly ${mode === "simulated" ? "simulated" : "replayed"} evidence to a separate demonstration run; no live incident is claimed.`,
                );
              })
            }
          >
            Run explicit {mode === "simulated" ? "demonstration" : "replay"}
          </button>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!loaded && <p role="status">Loading authorized security evidence…</p>}
      {loaded && !data && (
        <div className={styles.empty}>
          <h2>Workspace unavailable</h2>
          <p>
            This account needs an enabled, migrated cybersecurity workspace.
            Existing Chat, Knowledge and Digital Twins retain their own
            readiness.
          </p>
          <Link href="/">Return to Chat</Link>
        </div>
      )}
      {data && (
        <>
          <nav className={styles.tabs} aria-label="Cybersecurity views">
            {views.map((name) => (
              <button
                key={name}
                aria-current={view === name ? "page" : undefined}
                onClick={() => choose(name)}
              >
                {name}
              </button>
            ))}
          </nav>
          {view === "Overview" && (
            <>
              <div className={styles.grid}>
                <div className={styles.card}>
                  <span>Findings in this view</span>
                  <strong>{data.counts.findings}</strong>
                  <p>{data.counts.affected_assets} affected reviewed assets</p>
                  <button onClick={() => choose("Findings")}>
                    Review findings
                  </button>
                </div>
                <div className={styles.card}>
                  <span>Open investigations</span>
                  <strong>{data.counts.open_investigations}</strong>
                  <p>Resolution does not erase an observed condition.</p>
                  <button onClick={() => choose("Investigations")}>
                    Continue investigations
                  </button>
                </div>
                <div className={styles.card}>
                  <span>Control evidence coverage</span>
                  <strong>
                    {data.control_coverage.assessed} /{" "}
                    {data.control_coverage.denominator}
                  </strong>
                  <p>
                    {data.control_coverage.unknown} unknown ·{" "}
                    {data.control_coverage.stale} stale
                  </p>
                  <p className={styles.note}>
                    {data.control_coverage.definition}
                  </p>
                  <p
                    className={styles.note}
                  >{`Evaluated ${date(data.control_coverage.evaluated_at)} in ${mode} mode.`}</p>
                </div>
              </div>
              <div className={styles.split}>
                <Fields>
                  <h2>Source health</h2>
                  {!data.sources.length ? (
                    <div className={styles.empty}>
                      <h3>No sources configured</h3>
                      <p>
                        Register a reviewed source and import JSON or NDJSON. No
                        external service, model or 3D viewer is required.
                      </p>
                      <button onClick={() => choose("Sources")}>
                        Set up a source
                      </button>
                    </div>
                  ) : (
                    <ul className={styles.eventList}>
                      {data.source_health.map((h) => (
                        <li key={h.source_id}>
                          <strong>{sourceName(h.source_id)}</strong>{" "}
                          <Badge>Delivery {h.state}</Badge>
                          {h.reported_state && (
                            <Badge>Reported {h.reported_state}</Badge>
                          )}
                          <p>Last received: {date(h.last_received)}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className={styles.note}>
                    Fresh receipt indicates delivery, not authenticity or a
                    secure network. A source outage is a coverage gap.
                  </p>
                </Fields>
                <Fields>
                  <h2>Recent observations</h2>
                  {data.events.length ? (
                    <ul className={styles.eventList}>
                      {data.events.slice(0, 6).map((e) => (
                        <li key={e.id}>
                          <button
                            className={styles.linkButton}
                            onClick={() => {
                              setSelectedEvent(e);
                              choose("Events");
                            }}
                          >
                            {e.wire.summary}
                          </button>
                          <p>
                            {date(e.occurred_at)} · {e.mode} · {e.wire.quality}
                          </p>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>
                      No evidence in this mode. Unknown is not a clean security
                      assessment.
                    </p>
                  )}
                </Fields>
              </div>
            </>
          )}
          {view === "Assets" && (
            <div className={styles.split}>
              <Fields>
                <h2>Assets and posture</h2>
                {data.assets.length ? (
                  <div className={styles.scroll}>
                    <table className={styles.table}>
                      <thead>
                        <tr>
                          <th>Identity</th>
                          <th>Zone</th>
                          <th>Criticality</th>
                          <th>Findings</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.assets.map((a) => (
                          <tr key={a.id}>
                            <td>
                              <button
                                className={styles.linkButton}
                                onClick={() => void openAsset(a)}
                              >
                                {a.name}
                              </button>
                              <p className={styles.note}>{a.identity}</p>
                            </td>
                            <td>{a.zone}</td>
                            <td>{a.criticality}</td>
                            <td>
                              {
                                data.findings.filter((f) => f.asset_id === a.id)
                                  .length
                              }
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p>
                    No reviewed local assets yet. External names and addresses
                    do not establish equipment ownership.
                  </p>
                )}
                {selectedAsset && (
                  <section
                    tabIndex={-1}
                    ref={inspector}
                    className={styles.panel}
                    aria-label="Selected asset"
                  >
                    <h3>{selectedAsset.name}</h3>
                    <p>
                      {selectedAsset.zone} · {selectedAsset.criticality}{" "}
                      criticality
                    </p>
                    <p>Reviewed identity: {selectedAsset.identity}</p>
                    {selectedAsset.details.twin && (
                      <Link
                        href={`/industrial/twins?asset=${selectedAsset.details.twin.asset_id}&component=${selectedAsset.details.twin.component_id || ""}&security=1`}
                      >
                        Open reviewed Digital Twin mapping
                      </Link>
                    )}
                    <p className={styles.note}>
                      {selectedAsset.details.review_note}
                    </p>
                    <h4>Control evidence coverage</h4>
                    <ul>
                      {data.control_coverage.by_asset
                        .find((row) => row.asset_id === selectedAsset.id)
                        ?.controls.map((control) => (
                          <li key={control.control}>
                            {control.control.replaceAll("_", " ")} ·{" "}
                            {control.state} evidence
                          </li>
                        ))}
                    </ul>
                    <h4>Reviewed software inventory</h4>
                    {!assetReports.length && (
                      <p>
                        No reviewed inventory loaded for this asset. Unknown
                        firmware or version does not establish applicability.
                      </p>
                    )}
                    {assetReports.map((report) => (
                      <p key={report.id}>
                        <button
                          className={styles.linkButton}
                          onClick={() =>
                            void run(async () =>
                              setInventory(
                                await security<Inventory>(
                                  `/reports/${report.id}`,
                                ),
                              ),
                            )
                          }
                        >
                          {report.producer} · {report.component_count}{" "}
                          components · {report.advisory_count} reported
                          advisories · {report.mode}
                        </button>
                      </p>
                    ))}
                    {inventory && (
                      <div>
                        <p>
                          Imported {date(inventory.created_at)} ·{" "}
                          {inventory.details.mode} · exploitability{" "}
                          {inventory.details.exploitability}
                        </p>
                        <p className={styles.note}>
                          Original input SHA-256 {inventory.sha256}. Matches use
                          explicit imported report references.
                        </p>
                        <div className={styles.scroll}>
                          <table className={styles.table}>
                            <thead>
                              <tr>
                                <th>Software / firmware</th>
                                <th>Version</th>
                                <th>Reported advisories</th>
                              </tr>
                            </thead>
                            <tbody>
                              {inventory.details.document.components.map(
                                (component) => (
                                  <tr key={component["bom-ref"]}>
                                    <td>
                                      {component.name}
                                      <p className={styles.note}>
                                        {component.type}
                                      </p>
                                    </td>
                                    <td>
                                      {component.version ||
                                        "Unknown; applicability unconfirmed"}
                                    </td>
                                    <td>
                                      {inventory.details.document.vulnerabilities
                                        .filter((v) =>
                                          v.affects.some(
                                            (a) =>
                                              a.ref === component["bom-ref"],
                                          ),
                                        )
                                        .map((v) => (
                                          <p key={v.id}>
                                            {v.id} ·{" "}
                                            {v.ratings
                                              ?.map((r) => r.severity)
                                              .join(", ") || "Severity unknown"}
                                          </p>
                                        ))}
                                    </td>
                                  </tr>
                                ),
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    <h4>Applicable findings</h4>
                    {data.findings
                      .filter((f) => f.asset_id === selectedAsset.id)
                      .map((f) => (
                        <p key={f.id}>
                          <button
                            className={styles.linkButton}
                            onClick={() => void openFinding(f)}
                          >
                            {f.rule} · {f.severity}
                          </button>
                        </p>
                      ))}
                  </section>
                )}
              </Fields>
              <Fields>
                <h2>Register reviewed asset</h2>
                <form
                  onSubmit={(e) =>
                    submitted(e, async (f) => {
                      await security("/assets", "POST", {
                        name: f.get("name"),
                        identity: f.get("identity"),
                        zone: f.get("zone"),
                        criticality: f.get("criticality"),
                        review_note: f.get("review"),
                        ...(f.get("twin")
                          ? {
                              twin_asset_id: f.get("twin"),
                              ...(f.get("component")
                                ? { twin_component_id: f.get("component") }
                                : {}),
                            }
                          : {}),
                      });
                    })
                  }
                >
                  <label>
                    Asset name
                    <input name="name" required maxLength={120} />
                  </label>
                  <label>
                    Stable local identity
                    <input name="identity" required maxLength={128} />
                  </label>
                  <label>
                    Reviewed zone
                    <input name="zone" required maxLength={80} />
                  </label>
                  <label>
                    Criticality
                    <select name="criticality">
                      <option>unknown</option>
                      <option>low</option>
                      <option>medium</option>
                      <option>high</option>
                    </select>
                  </label>
                  <label>
                    Review note
                    <textarea
                      name="review"
                      required
                      minLength={8}
                      maxLength={1000}
                    />
                  </label>
                  <details>
                    <summary>Optional Digital Twin association</summary>
                    <p>
                      Use owned installed identities. A model node position is
                      not an asset identity.
                    </p>
                    <label>
                      Owned Twin asset UUID
                      <input name="twin" />
                    </label>
                    <label>
                      Owned installed component UUID
                      <input name="component" />
                    </label>
                  </details>
                  <button disabled={busy}>Register asset</button>
                </form>
              </Fields>
            </div>
          )}
          {view === "Events" && (
            <div className={styles.split}>
              <Fields>
                <h2>Security events</h2>
                <form
                  className={styles.actions}
                  onSubmit={(e) => {
                    e.preventDefault();
                    void run(async () => {
                      const result = await security<{
                        items: SecurityEvent[];
                        next: string | null;
                      }>(
                        `/events?mode=${mode}&q=${encodeURIComponent(search)}`,
                      );
                      setSearchEvents(result.items);
                      setEventCursor(result.next || "");
                      setAppliedSearch(search);
                    });
                  }}
                >
                  <label>
                    Search summaries
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      maxLength={128}
                    />
                  </label>
                  <button disabled={busy}>Search evidence</button>
                  <button
                    type="button"
                    onClick={() => {
                      setSearch("");
                      setSearchEvents(null);
                      setEventCursor(undefined);
                      setAppliedSearch("");
                    }}
                  >
                    Clear search
                  </button>
                </form>
                <p className={styles.note}>
                  At most 100 events per page. Occurred and received times are
                  separate.
                </p>
                <ul className={styles.eventList}>
                  {shownEvents.map((e) => (
                    <li key={e.id}>
                      <button
                        className={styles.linkButton}
                        onClick={() => {
                          setSelectedEvent(e);
                          focusInspector();
                        }}
                      >
                        {e.wire.summary}
                      </button>
                      <p>
                        <Badge>{e.mode}</Badge> <Badge>{e.wire.quality}</Badge>{" "}
                        {e.event_type}
                      </p>
                      <p className={styles.note}>
                        {sourceName(e.source_id)} · {date(e.occurred_at)}
                      </p>
                    </li>
                  ))}
                </ul>
                {nextEvents && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        const page = await security<{
                          items: SecurityEvent[];
                          next: string | null;
                        }>(
                          `/events?mode=${mode}&before=${nextEvents}&q=${encodeURIComponent(appliedSearch)}`,
                        );
                        setSearchEvents([
                          ...shownEvents,
                          ...page.items.filter(
                            (item) =>
                              !shownEvents.some(
                                (known) => known.id === item.id,
                              ),
                          ),
                        ]);
                        setEventCursor(page.next || "");
                      })
                    }
                  >
                    Load earlier observations
                  </button>
                )}
                {!shownEvents.length && (
                  <p>
                    No matching evidence. Check mode, source health and import
                    status.
                  </p>
                )}
              </Fields>
              <section
                className={styles.panel}
                tabIndex={-1}
                ref={inspector}
                aria-label="Selected event"
              >
                <h2>Evidence detail</h2>
                {selectedEvent ? (
                  <>
                    <p>{selectedEvent.wire.summary}</p>
                    <p>Asset: {assetName(selectedEvent.asset_id)}</p>
                    <dl>
                      <dt>Occurred</dt>
                      <dd>{date(selectedEvent.occurred_at)}</dd>
                      <dt>Received</dt>
                      <dd>{date(selectedEvent.created_at)}</dd>
                      <dt>Evidence expiry</dt>
                      <dd>{date(selectedEvent.expires_at)}</dd>
                      <dt>Provenance</dt>
                      <dd>
                        {selectedEvent.provenance.basis}
                        {selectedEvent.provenance.late ? " · late arrival" : ""}
                      </dd>
                    </dl>
                    <h3>Typed attributes</h3>
                    <pre>{json(selectedEvent.wire.attributes)}</pre>
                    <p className={styles.note}>
                      Content reference {selectedEvent.sha256}. Database history
                      is append-only through this application, not tamper-proof
                      against infrastructure administrators.
                    </p>
                  </>
                ) : (
                  <p>
                    Select an observation to inspect its source, quality and
                    bounded attributes.
                  </p>
                )}
              </section>
            </div>
          )}
          {view === "Findings" && (
            <div className={styles.split}>
              <Fields>
                <h2>Deterministic findings</h2>
                <p className={styles.note}>
                  Severity, confidence, criticality and investigation priority
                  describe different things.
                </p>
                {data.findings.length ? (
                  <div className={styles.scroll}>
                    <table className={styles.table}>
                      <thead>
                        <tr>
                          <th>Finding</th>
                          <th>Severity / evidence</th>
                          <th>Priority</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.findings.map((f) => (
                          <tr key={f.id}>
                            <td>
                              <button
                                className={styles.linkButton}
                                onClick={() => void openFinding(f)}
                              >
                                {f.rule.replaceAll("_", " ")}
                              </button>
                              <p className={styles.note}>
                                {assetName(f.asset_id)}
                              </p>
                            </td>
                            <td>
                              <Badge>{f.severity}</Badge>{" "}
                              <Badge>{f.confidence}</Badge>
                              <p>{f.mode}</p>
                            </td>
                            <td>{f.priority} / 100</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p>
                    No findings in this mode. This does not mean that assets are
                    secure or fully assessed.
                  </p>
                )}
              </Fields>
              <section
                className={styles.panel}
                tabIndex={-1}
                ref={inspector}
                aria-label="Selected finding"
              >
                <h2>Finding explanation</h2>
                {selectedFinding ? (
                  <>
                    <h3>{selectedFinding.rule.replaceAll("_", " ")}</h3>
                    <p>{selectedFinding.details.explanation}</p>
                    <p>
                      <Badge>{selectedFinding.mode}</Badge>{" "}
                      <Badge>{selectedFinding.severity}</Badge>{" "}
                      {selectedFinding.confidence} evidence
                    </p>
                    <p>
                      First seen {date(selectedFinding.first_seen)} · Last seen{" "}
                      {date(selectedFinding.last_seen)}
                    </p>
                    <p className={styles.note}>
                      {selectedFinding.rule_version} ·{" "}
                      {selectedFinding.occurrences} evidence versions
                    </p>
                    <h4>Observed</h4>
                    <pre>{json(selectedFinding.details.observed)}</pre>
                    <h4>Expected / reviewed baseline</h4>
                    <pre>{json(selectedFinding.details.expected)}</pre>
                    <p className={styles.note}>
                      {selectedFinding.details.priority_formula}
                    </p>
                    {selectedAsset && (
                      <button onClick={() => void openAsset(selectedAsset)}>
                        Follow asset: {selectedAsset.name}
                      </button>
                    )}
                    <h4>Original evidence</h4>
                    {selectedFinding.details.evidence.map((e) => (
                      <p key={e.id}>
                        <button
                          className={styles.linkButton}
                          onClick={() => {
                            setSelectedEvent(e);
                            choose("Events");
                          }}
                        >
                          {e.wire.summary} · {date(e.occurred_at)}
                        </button>
                      </p>
                    ))}
                    <button
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const value = await security<{ id: string }>(
                            "/investigations",
                            "POST",
                            {
                              finding_id: selectedFinding.id,
                              title: `Review ${selectedFinding.rule}`,
                            },
                          );
                          setCaseDetail(
                            await security<CaseDetail>(
                              `/investigations/${value.id}`,
                            ),
                          );
                          choose("Investigations");
                          await refresh();
                        })
                      }
                    >
                      Create investigation
                    </button>
                  </>
                ) : (
                  <p>
                    Select a finding to inspect its rule, source and evidence
                    before making a decision.
                  </p>
                )}
              </section>
            </div>
          )}
          {view === "Investigations" && (
            <div className={styles.split}>
              <Fields>
                <h2>Investigations</h2>
                <p>
                  Assigned to the current owner. Owner review is not independent
                  approval.
                </p>
                {data.investigations.length ? (
                  <ul className={styles.eventList}>
                    {data.investigations.map((c) => (
                      <li key={c.id}>
                        <button
                          className={styles.linkButton}
                          onClick={() => void openCase(c.id)}
                        >
                          {c.title}
                        </button>
                        <p>
                          <Badge>{c.status}</Badge> Priority {c.priority} ·{" "}
                          {date(c.updated_at)}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>
                    Open a finding and create an investigation to preserve its
                    evidence and decision history.
                  </p>
                )}
              </Fields>
              <section
                className={styles.panel}
                tabIndex={-1}
                ref={inspector}
                aria-label="Selected investigation"
              >
                <h2>Investigation detail</h2>
                {caseDetail ? (
                  <>
                    <h3>{caseDetail.investigation.title}</h3>
                    <p>
                      <Badge>{caseDetail.investigation.status}</Badge> Revision{" "}
                      {caseDetail.investigation.revision}
                    </p>
                    {caseDetail.acceptance_expired && (
                      <p role="alert">
                        Risk acceptance has expired. Review the condition again.
                      </p>
                    )}
                    <details>
                      <summary>Original decision context</summary>
                      <pre>{json(caseDetail.investigation.snapshot)}</pre>
                    </details>
                    <p className={styles.note}>
                      Snapshot {caseDetail.investigation.sha256}. Later evidence
                      and rules do not rewrite this snapshot.
                    </p>
                    <h4>Decision timeline</h4>
                    <ul className={styles.eventList}>
                      {caseDetail.evidence.history.map((a) => (
                        <li key={a.id}>
                          <button
                            className={styles.linkButton}
                            onClick={() =>
                              void run(async () =>
                                setDecisionSnapshot(
                                  await security<Record<string, unknown>>(
                                    `/actions/${a.id}`,
                                  ),
                                ),
                              )
                            }
                          >
                            {a.kind}
                          </button>{" "}
                          · {date(a.created_at)}
                          <p>
                            {a.details.note ||
                              "Investigation opened with an immutable evidence snapshot."}
                          </p>
                        </li>
                      ))}
                    </ul>
                    {caseDetail.evidence.history_next && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            const older = await security<{
                              history: Action[];
                              history_next: string | null;
                            }>(
                              `/investigations/${caseDetail.investigation.id}/actions?before=${caseDetail.evidence.history_next}`,
                            );
                            setCaseDetail((current) =>
                              current
                                ? {
                                    ...current,
                                    evidence: {
                                      ...current.evidence,
                                      history: [
                                        ...older.history,
                                        ...current.evidence.history,
                                      ],
                                      history_next: older.history_next,
                                    },
                                  }
                                : current,
                            );
                          })
                        }
                      >
                        Load earlier decisions
                      </button>
                    )}
                    {decisionSnapshot && (
                      <details open>
                        <summary>Immutable decision snapshot</summary>
                        <pre>{json(decisionSnapshot)}</pre>
                      </details>
                    )}
                    {!!caseDetail.summaries?.length && (
                      <details>
                        <summary>
                          Saved investigation reports (
                          {caseDetail.summaries.length})
                        </summary>
                        <ul>
                          {caseDetail.summaries.map((report) => (
                            <li key={report.id}>
                              <button
                                className={styles.linkButton}
                                onClick={() => setSummary(report)}
                              >
                                {date(report.created_at)} ·{" "}
                                {String(report.result.status)}
                              </button>
                              <p className={styles.note}>
                                Context checksum {report.sha256}
                              </p>
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                    <form
                      onSubmit={(e) =>
                        submitted(e, async (f) => {
                          const id = caseDetail.investigation.id;
                          await security(
                            `/investigations/${id}/decisions`,
                            "POST",
                            {
                              revision: caseDetail.investigation.revision,
                              action: f.get("action"),
                              note: f.get("note"),
                              evidence_ids: f.getAll("evidence"),
                              ...(f.get("expiry")
                                ? {
                                    acceptance_until: new Date(
                                      String(f.get("expiry")),
                                    ).toISOString(),
                                  }
                                : {}),
                            },
                          );
                          setCaseDetail(
                            await security<CaseDetail>(`/investigations/${id}`),
                          );
                        })
                      }
                    >
                      <label>
                        Decision
                        <select name="action">
                          <option value="note">Add note</option>
                          <option value="acknowledge">Acknowledge</option>
                          <option value="investigate">Investigate</option>
                          <option value="resolve">Resolve with evidence</option>
                          <option value="dismiss">Reasoned dismissal</option>
                          <option value="accept_risk">
                            Accept risk temporarily
                          </option>
                          <option value="reopen">Reopen</option>
                        </select>
                      </label>
                      <label>
                        Decision note
                        <textarea
                          name="note"
                          required
                          minLength={8}
                          maxLength={2000}
                        />
                      </label>
                      <label>
                        Supporting evidence
                        <select name="evidence" multiple>
                          {caseDetail.evidence.finding.details.evidence.map(
                            (e) => (
                              <option key={e.id} value={e.id}>
                                {e.wire.summary} · {date(e.occurred_at)}
                              </option>
                            ),
                          )}
                        </select>
                      </label>
                      <label>
                        Risk acceptance expiry (local time; within 30 days)
                        <input name="expiry" type="datetime-local" />
                      </label>
                      <button disabled={busy}>Record decision</button>
                    </form>
                    <h4>Evidence-grounded assistance</h4>
                    <p>
                      Prepare a deterministic checklist without inference.
                      Optional assistance drafts hypotheses and cannot change
                      findings or close an investigation.
                    </p>
                    <div className={styles.actions}>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            setSummary(
                              await security<Record<string, unknown>>(
                                "/summaries",
                                "POST",
                                {
                                  investigation_id: caseDetail.investigation.id,
                                  expected_sha256:
                                    caseDetail.investigation.sha256,
                                  assist: false,
                                },
                              ),
                            );
                          })
                        }
                      >
                        Prepare checklist
                      </button>
                      {ready?.ai_enabled && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            void run(async () => {
                              setSummary(
                                await security<Record<string, unknown>>(
                                  "/summaries",
                                  "POST",
                                  {
                                    investigation_id:
                                      caseDetail.investigation.id,
                                    expected_sha256:
                                      caseDetail.investigation.sha256,
                                    assist: true,
                                  },
                                ),
                              );
                            })
                          }
                        >
                          Draft hypotheses for review
                        </button>
                      )}
                    </div>
                    {summary && (
                      <pre aria-label="Investigation checklist">
                        {json(summary.result)}
                      </pre>
                    )}
                  </>
                ) : (
                  <p>
                    Select an investigation. The full investigation works
                    without a model or 3D browser.
                  </p>
                )}
              </section>
            </div>
          )}
          {view === "Sources" && (
            <>
              <div className={styles.split}>
                <Fields>
                  <h2>Sources and import</h2>
                  <label>
                    Reviewed source
                    <select
                      value={sourceId}
                      onChange={(e) => {
                        setSourceId(e.target.value);
                        setExportNext({});
                        setToken("");
                        setInput("");
                      }}
                    >
                      <option value="">Select a source</option>
                      {data.sources.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} · {s.namespace}
                          {s.revoked_at ? " · revoked" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedSource && (
                    <>
                      <p>
                        {selectedSource.scope === "operator"
                          ? "Native application evidence is produced only by actual server decisions."
                          : "This source can submit evidence only under its configured producer identity and modes."}
                      </p>
                      <p>Modes: {selectedSource.config.modes.join(", ")}</p>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void run(async () =>
                            setConfigurationDetail(
                              await security<Record<string, unknown>>(
                                `/sources/${sourceId}`,
                              ),
                            ),
                          )
                        }
                      >
                        Inspect source configuration
                      </button>
                      {selectedSource.scope === "owner" &&
                        !selectedSource.revoked_at && (
                          <>
                            <label>
                              Evidence file (JSON or NDJSON; at most 1 MiB)
                              <input
                                type="file"
                                accept=".json,.ndjson,application/json,application/x-ndjson"
                                onChange={(e) =>
                                  void importFile(e.target.files?.[0])
                                }
                              />
                            </label>
                            <label>
                              Evidence batch
                              <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                maxLength={1048576}
                                spellCheck={false}
                              />
                            </label>
                            <div className={styles.actions}>
                              <button
                                disabled={busy || !input}
                                onClick={() =>
                                  void run(async () => {
                                    let ndjson = false;
                                    try {
                                      const candidate = JSON.parse(input);
                                      if (
                                        !candidate ||
                                        !Array.isArray(candidate.events)
                                      )
                                        throw new Error("not a JSON batch");
                                    } catch {
                                      ndjson = true;
                                    }
                                    const response = await fetch(
                                      `/api/v1/cybersecurity/sources/${sourceId}/imports`,
                                      {
                                        method: "POST",
                                        credentials: "same-origin",
                                        headers: {
                                          "Content-Type": ndjson
                                            ? "application/x-ndjson"
                                            : "application/json",
                                          "X-CSRF-Token": csrf(),
                                        },
                                        body: input,
                                      },
                                    );
                                    if (!response.ok) {
                                      const err = await response.json();
                                      throw new Error(
                                        err.error?.message || "Import rejected",
                                      );
                                    }
                                    const receipt = await response.json();
                                    setNotice(
                                      `Imported ${receipt.inserted} observations; ${receipt.duplicates} identical retries.`,
                                    );
                                    await refresh();
                                  })
                                }
                              >
                                Import evidence
                              </button>
                              <button
                                disabled={busy}
                                onClick={() => {
                                  if (mode === "live") {
                                    setError(
                                      "Select simulated or replay mode before preparing an example.",
                                    );
                                    return;
                                  }
                                  setInput(
                                    json(
                                      eventExample(
                                        selectedSource.namespace,
                                        mode,
                                      ),
                                    ),
                                  );
                                }}
                              >
                                Prepare labeled example
                              </button>
                              <button
                                disabled={busy}
                                onClick={() =>
                                  void run(async () => {
                                    await security(
                                      `/sources/${sourceId}/revoke`,
                                      "POST",
                                    );
                                    setToken("");
                                    await refresh();
                                    setNotice(
                                      "Source credential revoked. Retained evidence is still available.",
                                    );
                                  })
                                }
                              >
                                Revoke ingestion credential
                              </button>
                            </div>
                            <p className={styles.note}>
                              Batches: at most 100 events, 8 KiB per event.
                              Unsupported versions, fields, mappings and
                              conflicting IDs are rejected. No remote endpoint
                              is fetched.
                            </p>
                          </>
                        )}
                      {selectedSource.revoked_at && (
                        <p>This source is revoked; ingestion is closed.</p>
                      )}
                    </>
                  )}
                  {token && (
                    <div role="status" className={styles.panel}>
                      <h3>One-time scoped credential</h3>
                      <p>
                        Store in the collector’s private credential store. It
                        grants ingestion only and is never saved in this
                        browser’s storage.
                      </p>
                      <label>
                        New ingestion credential
                        <input
                          type="password"
                          value={token}
                          readOnly
                          autoComplete="off"
                        />
                      </label>
                      <button onClick={() => setToken("")}>
                        Dismiss credential
                      </button>
                    </div>
                  )}
                  <h3>Create source</h3>
                  <form
                    onSubmit={(e) =>
                      submitted(e, async (f) => {
                        const result = await security<{
                          id: string;
                          ingestion_token: string;
                        }>("/sources", "POST", {
                          name: f.get("name"),
                          namespace: f.get("namespace"),
                          modes: [mode],
                          expected_interval_seconds: Number(f.get("interval")),
                          endpoint_refs: String(f.get("endpoints") || "")
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean),
                          review_note: f.get("review"),
                        });
                        setSourceId(result.id);
                        setToken(result.ingestion_token);
                      })
                    }
                  >
                    <label>
                      Source name
                      <input name="name" required maxLength={120} />
                    </label>
                    <label>
                      Producer namespace
                      <input name="namespace" required maxLength={64} />
                    </label>
                    <p>
                      Allowed mode: <strong>{mode}</strong>. Simulated and
                      replay sources remain separate from live evidence.
                    </p>
                    <label>
                      Expected interval (seconds)
                      <input
                        name="interval"
                        type="number"
                        min={10}
                        max={86400}
                        defaultValue={300}
                        required
                      />
                    </label>
                    <label>
                      Reviewed certificate endpoint references (comma separated)
                      <input name="endpoints" maxLength={1000} />
                    </label>
                    <label>
                      Source review note
                      <textarea
                        name="review"
                        required
                        minLength={8}
                        maxLength={1000}
                      />
                    </label>
                    <button disabled={busy}>Create scoped source</button>
                  </form>
                </Fields>
                <div>
                  <Fields>
                    <h2>Reviewed asset mapping</h2>
                    <form
                      onSubmit={(e) =>
                        submitted(e, async (f) => {
                          if (!sourceId)
                            throw new Error("Select a source first");
                          await security(
                            `/sources/${sourceId}/mappings`,
                            "POST",
                            {
                              asset_id: f.get("asset"),
                              namespace: f.get("namespace"),
                              external_asset: f.get("external"),
                              external_component: f.get("component") || null,
                              review_note: f.get("review"),
                            },
                          );
                        })
                      }
                    >
                      <label>
                        Local reviewed asset
                        <select name="asset" required>
                          <option value="">Select asset</option>
                          {data.assets.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        External asset namespace
                        <input name="namespace" required maxLength={128} />
                      </label>
                      <label>
                        External asset reference
                        <input name="external" required maxLength={128} />
                      </label>
                      <label>
                        External component reference (optional)
                        <input name="component" maxLength={128} />
                      </label>
                      <label>
                        Mapping review note
                        <textarea
                          name="review"
                          required
                          minLength={8}
                          maxLength={1000}
                        />
                      </label>
                      <button disabled={busy || !sourceId}>
                        Review mapping
                      </button>
                    </form>
                    {data.mappings
                      .filter((m) => m.source_id === sourceId)
                      .map((m) => (
                        <p key={m.id}>
                          {m.external_namespace} / {m.external_asset} →{" "}
                          {assetName(m.asset_id)}
                        </p>
                      ))}
                  </Fields>
                  <Fields>
                    <h2>Offline inventory report</h2>
                    <p>
                      Supported profile: CycloneDX 1.6 flat subset. At most 250
                      components, 100 advisories and 2 MiB. Reported
                      applicability is separate from verified exploitability.
                    </p>
                    <form
                      onSubmit={(e) =>
                        submitted(e, async (f) => {
                          const file = f.get("report") as File;
                          if (!sourceId || !file?.size)
                            throw new Error("Select source, asset and report");
                          if (file.size > 2097152)
                            throw new Error("Inventory report exceeds 2 MiB");
                          const response = await fetch(
                            `/api/v1/cybersecurity/sources/${sourceId}/reports?asset_id=${f.get("asset")}&mode=${mode}${mode !== "live" ? `&run_id=${encodeURIComponent(String(f.get("run")))}` : ""}`,
                            {
                              method: "POST",
                              credentials: "same-origin",
                              headers: {
                                "Content-Type": "application/json",
                                "X-CSRF-Token": csrf(),
                              },
                              body: file,
                            },
                          );
                          if (!response.ok) {
                            const error = await response.json();
                            throw new Error(
                              error.error?.message ||
                                "Inventory import rejected",
                            );
                          }
                          const receipt = await response.json();
                          setNotice(
                            `Inventory imported. Original input SHA-256 ${receipt.sha256}.`,
                          );
                        })
                      }
                    >
                      <label>
                        Reviewed affected asset
                        <select name="asset" required>
                          {data.assets.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        CycloneDX JSON
                        <input
                          name="report"
                          type="file"
                          accept=".json,application/json"
                          required
                        />
                      </label>
                      {mode !== "live" && (
                        <label>
                          Scenario or replay run ID
                          <input name="run" required maxLength={128} />
                        </label>
                      )}
                      <button disabled={busy || !sourceId}>
                        Import reviewed inventory
                      </button>
                    </form>
                  </Fields>
                </div>
              </div>
              {selectedSource && (
                <div className={styles.split}>
                  <Fields>
                    <h2>Versioned detection policy</h2>
                    <p>
                      Changes create a new version. Earlier findings and human
                      decisions retain their original context.
                    </p>
                    <form
                      onSubmit={(e) =>
                        submitted(e, async (f) => {
                          await security(
                            `/sources/${sourceId}/policies`,
                            "POST",
                            {
                              auth_threshold: Number(f.get("auth")),
                              denial_threshold: Number(f.get("denials")),
                              window_seconds: Number(f.get("window")),
                              certificate_warning_days: Number(f.get("days")),
                              review_note: f.get("review"),
                            },
                          );
                        })
                      }
                    >
                      <label>
                        Failed authentication threshold
                        <input
                          name="auth"
                          type="number"
                          defaultValue={5}
                          min={2}
                          max={100}
                          required
                        />
                      </label>
                      <label>
                        Authorization denial threshold
                        <input
                          name="denials"
                          type="number"
                          defaultValue={3}
                          min={2}
                          max={100}
                          required
                        />
                      </label>
                      <label>
                        Window in seconds
                        <input
                          name="window"
                          type="number"
                          defaultValue={300}
                          min={30}
                          max={3600}
                          required
                        />
                      </label>
                      <label>
                        Certificate warning days
                        <input
                          name="days"
                          type="number"
                          defaultValue={30}
                          min={1}
                          max={90}
                          required
                        />
                      </label>
                      <label>
                        Policy review note
                        <textarea
                          name="review"
                          required
                          minLength={8}
                          maxLength={1000}
                        />
                      </label>
                      <button disabled={busy}>Save policy version</button>
                    </form>
                    {data.policies
                      .filter((p) => p.source_id === sourceId)
                      .map((p) => (
                        <p key={p.id}>
                          <button
                            className={styles.linkButton}
                            onClick={() =>
                              void run(async () =>
                                setConfigurationDetail(
                                  await security<Record<string, unknown>>(
                                    `/policies/${p.id}`,
                                  ),
                                ),
                              )
                            }
                          >
                            Inspect policy version {p.version}
                          </button>{" "}
                          · <code>{p.sha256.slice(0, 16)}</code>
                        </p>
                      ))}
                  </Fields>
                  <Fields>
                    <h2>Accepted baseline and allowlist</h2>
                    <p>
                      No configuration drift or unknown-identity finding is
                      inferred without this reviewed scope.
                    </p>
                    <form
                      onSubmit={(e) =>
                        submitted(e, async (f) => {
                          const list = (name: string) =>
                            String(f.get(name) || "")
                              .split(",")
                              .map((s) => s.trim())
                              .filter(Boolean);
                          await security(
                            `/sources/${sourceId}/baselines`,
                            "POST",
                            {
                              revision: f.get("revision"),
                              relevant_keys: list("keys"),
                              allowed_identities: list("identities"),
                              input_refs: list("inputs"),
                              review_note: f.get("review"),
                            },
                          );
                        })
                      }
                    >
                      <label>
                        Accepted revision
                        <input name="revision" required maxLength={128} />
                      </label>
                      <label>
                        Security-relevant changed-key names (comma separated)
                        <input name="keys" maxLength={2048} />
                      </label>
                      <label>
                        Allowed identity references (comma separated)
                        <input name="identities" maxLength={4096} />
                      </label>
                      <label>
                        Reviewed observation input references (comma separated)
                        <input name="inputs" maxLength={2048} />
                      </label>
                      <label>
                        Baseline review note
                        <textarea
                          name="review"
                          required
                          minLength={8}
                          maxLength={1000}
                        />
                      </label>
                      <button disabled={busy}>Accept baseline revision</button>
                    </form>
                    {data.baselines
                      .filter((b) => b.source_id === sourceId)
                      .map((b) => (
                        <p key={b.id}>
                          <button
                            className={styles.linkButton}
                            onClick={() =>
                              void run(async () =>
                                setConfigurationDetail(
                                  await security<Record<string, unknown>>(
                                    `/baselines/${b.id}`,
                                  ),
                                ),
                              )
                            }
                          >
                            Inspect reviewed revision: {b.revision}
                          </button>
                        </p>
                      ))}
                  </Fields>
                </div>
              )}
              <Fields>
                <h2>Export and boundaries</h2>
                {configurationDetail && (
                  <details open>
                    <summary>Authorized versioned configuration</summary>
                    <pre>{json(configurationDetail)}</pre>
                  </details>
                )}
                <p>
                  Exports contain only currently authorized evidence in this
                  mode. Credentials are excluded. JSON and NDJSON remain inert
                  structured data; no CSV formulas are generated.
                </p>
                <div className={styles.actions}>
                  {["json", "ndjson"].map((format) => (
                    <div key={format} className={styles.actions}>
                      <button
                        disabled={busy}
                        onClick={() => void downloadEvidence(format)}
                      >
                        Export {format.toUpperCase()} page
                      </button>
                      {exportNext[format] && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            void downloadEvidence(format, exportNext[format])
                          }
                        >
                          Export next {format.toUpperCase()} page
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <p className={styles.note}>
                  No automatic remediation, active discovery, packet capture or
                  device control. Ordinary users cannot inspect global platform
                  security decisions. Retention and larger personal exports are
                  available through Account settings and the documented operator
                  process.
                </p>
              </Fields>
            </>
          )}
        </>
      )}
    </FeatureShell>
  );
}
export default function Page() {
  return (
    <RequireSession
      title="Cybersecurity"
      destination="/industrial/cybersecurity"
    >
      <Suspense fallback={<p role="status">Preparing security workspace…</p>}>
        <WorkspacePage />
      </Suspense>
    </RequireSession>
  );
}
