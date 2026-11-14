"use client";
import { useEffect, useRef, useState } from "react";
import IndustrialImport, {IndustrialFactsTool} from "../../components/industrial-import";
import RequireSession from "../../components/require-session";
import FeatureShell from "../../components/feature-shell";
import { useDraftNavigation } from "../../components/draft-navigation";
import { api, ApiError, type InvestigationOut } from "../../lib/api";
import { useLocale } from "../../lib/i18n";
import styles from "./industrial.module.css";

type Facts = {
  event_count: number;
  known_downtime_seconds: number;
  distinct_downtime_episodes: number;
  downtime_complete: boolean;
  incomplete_event_ids: string[];
  timeline: {
    id: string;
    clipped_start: string;
    clipped_end: string;
    source: string;
    quality: string;
  }[];
};
type Source = {
  id: string;
  version: string;
  title: string;
  anchor: string;
  text: string;
  sha256: string;
  rights: string;
};
type Coverage = {
  missing: string[];
  stale_signal_ids: string[];
  reference_conflict: boolean;
  signal_coverage: string;
};
type Explanation = {
  abstained: boolean;
  limitations: string[];
  hypotheses: {
    statement: string;
    human_review: string;
    quote: string;
    citations: { document_id: string; version: string; anchor: string }[];
  }[];
};
type Payload = {
  selection: { asset_id: string; start: string; end: string };
  snapshot_sha256: string;
  facts: Facts;
  coverage: Coverage;
  evidence: {
    fixture_version: string;
    metadata_version: string;
    references: Source[];
    signals: {
      id: string;
      value: number;
      unit: string;
      timestamp: string;
      quality: string;
    }[];
  };
  explanation: Explanation | null;
  generation: {
    mode: string;
    backend: string;
    model: string;
    revision: string | null;
    input_tokens: number | null;
    output_tokens: number | null;
    latency_ms: number | null;
    cost: number | null;
  } | null;
  error: string | null;
  draft: string | null;
  review: { decision: string; scope: string; reviewed_revision: number } | null;
};
type Investigation = Omit<InvestigationOut, "payload"> & { payload: Payload };
const decode = (row: InvestigationOut) => row as Investigation;
const scenarios = [
  "reference",
  "no_stops",
  "overlap",
  "boundary",
  "open_event",
  "stale",
  "conflict",
] as const;
type Scenario = (typeof scenarios)[number];

export default function Industrial() {
  return (
    <RequireSession destination="/industrial" title="Industrial Investigation">
      <Workspace />
    </RequireSession>
  );
}

function Workspace() {
  const { locale } = useLocale(),
    de = locale === "de";
  const text = (en: string, german: string) => (de ? german : en);
  const [listState, setListState] = useState<"loading" | "loaded" | "failed">("loading");
  const [importAvailable, setImportAvailable] = useState(false);
  const [assets, setAssets] = useState<{ id: string; name: string }[]>([]);
  const [items, setItems] = useState<Investigation[]>([]),
    [selected, setSelected] = useState<Investigation | null>(null);
  const [asset, setAsset] = useState("demo-press-01"),
    [scenario, setScenario] = useState<Scenario>("reference");
  const [start, setStart] = useState("2026-10-20T09:00"),
    [end, setEnd] = useState("2026-10-20T10:00");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [generating, setGenerating] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [draft, setDraft] = useState(""),
    [baseline, setBaseline] = useState("");
  const [editing, setEditing] = useState(false),
    [reviewNote, setReviewNote] = useState("");
  const [preview, setPreview] = useState<{
    facts: Facts;
    coverage: Coverage;
  } | null>(null);
  const pending = useRef(false),
    generation = useRef<AbortController | null>(null);
  const cancelPending = useRef(false),
    lifetime = useRef<AbortController | null>(null),
    latest = useRef<Investigation | null>(null);
  const locked = busy || cancelling;
  const createId = useRef<string | null>(null);
  const navigate = useDraftNavigation(
    draft !== baseline || Boolean(reviewNote),
    locked,
    () => {
      setDraft(baseline);
      setReviewNote("");
    },
  );
  const payload = selected?.payload;

  function requestSignal(milliseconds = 25000) {
    return AbortSignal.any([
      AbortSignal.timeout(milliseconds),
      ...(lifetime.current ? [lifetime.current.signal] : []),
    ]);
  }
  function accept(row: InvestigationOut) {
    const incoming = decode(row),
      known = latest.current;
    const value =
      known?.id === incoming.id && known.revision > incoming.revision
        ? known
        : incoming;
    latest.current = value;
    setSelected(value);
    setItems((old) => [value, ...old.filter((item) => item.id !== value.id)]);
    return value;
  }
  function choose(value: Investigation | null) {
    if (pending.current || cancelPending.current) return;
    navigate(() => {
      latest.current = value;
      setSelected(value);
      setDraft(value?.payload.draft || "");
      setBaseline(value?.payload.draft || "");
      setEditing(Boolean(value?.payload.draft));
      setReviewNote("");
      setError("");
      setNotice("");
    });
  }
  function message(reason: unknown) {
    if (reason instanceof Error && reason.name === "TimeoutError")
      return text(
        "The request timed out and may still finish on the server. Your entries are kept; refresh saved state before repeating a change.",
        "Die Anfrage hat das Zeitlimit erreicht und kann auf dem Server noch abgeschlossen werden. Deine Eingaben bleiben erhalten; lade vor einer erneuten Änderung den gespeicherten Zustand.",
      );
    if (reason instanceof ApiError) {
      if (reason.status === 401)
        return text(
          "Session expired. Your draft is kept; sign in before trying again.",
          "Sitzung abgelaufen. Dein Entwurf bleibt erhalten; melde dich erneut an.",
        );
      if (reason.code === "revision_conflict")
        return text(
          "A newer revision exists. Your entries are kept; reopen the saved investigation before making a deliberate update.",
          "Eine neuere Version ist vorhanden. Deine Eingaben bleiben erhalten; öffne die gespeicherte Untersuchung vor einer bewussten Änderung.",
        );
      if (reason.code === "industrial_demo_disabled")
        return text(
          "The synthetic demonstration is not enabled on this environment.",
          "Die synthetische Demonstration ist in dieser Umgebung nicht aktiviert.",
        );
      if (reason.status === 404)
        return text(
          "This investigation was not found or is not available to this account.",
          "Diese Untersuchung wurde nicht gefunden oder ist für dieses Konto nicht verfügbar.",
        );
      if (reason.status === 429)
        return text(
          "Generation capacity is busy or its budget is exhausted. Facts and draft are retained; retry only when available.",
          "Generierungskapazität oder Budget erschöpft. Fakten und Entwurf bleiben erhalten.",
        );
    }
    return text(
      "The request could not be confirmed. Your entries are kept. Reopen the investigation to check its saved state before retrying.",
      "Die Anfrage konnte nicht bestätigt werden. Eingaben bleiben erhalten. Prüfe den gespeicherten Zustand vor einem erneuten Versuch.",
    );
  }
  useEffect(() => {
    const abort = new AbortController();
    lifetime.current = abort;
    const signal = AbortSignal.any([abort.signal, AbortSignal.timeout(25000)]);
    api("GET /industrial/assets", { signal })
      .then((catalog) => {
        if (abort.signal.aborted) return;
        if (!Array.isArray(catalog?.items) || !catalog.items.every(item =>
          item && typeof item.id === "string" && item.id.length > 0 &&
          typeof item.name === "string" && item.name.length > 0))
          throw new Error("Invalid Industrial asset catalog");
        setAssets(catalog.items as { id: string; name: string }[]);
        setImportAvailable(catalog.import_enabled === true);
      })
      .catch((reason) => {
        if (!abort.signal.aborted) setError(message(reason));
      });
    api("GET /industrial/investigations", { signal })
      .then((saved) => {
        if (abort.signal.aborted) return;
        const loaded = saved.items.map(decode);
        // Preserve records accepted while this initial snapshot was in flight.
        setItems((current) => [
          ...current,
          ...loaded.filter((row) => !current.some((known) => known.id === row.id)),
        ]);
        setListState("loaded");
      })
      .catch((reason) => {
        if (!abort.signal.aborted) {
          setListState("failed");
          setError(message(reason));
        }
      });
    return () => {
      abort.abort();
      generation.current?.abort();
    };
    // Error language follows the request's current interface language; data stays mounted on changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  async function action(run: () => Promise<void>) {
    if (pending.current || cancelPending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await run();
    } catch (reason) {
      setError(message(reason));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  async function inspect(event: React.FormEvent) {
    event.preventDefault();
    await action(async () => {
      const query = new URLSearchParams({
        asset_id: asset,
        scenario,
        start: start + ":00Z",
        end: end + ":00Z",
      });
      // Query parameters are explicit evidence selection, never a source path or provider URL.
      const { call } = await import("../../lib/api");
      const response = await call(
        "/industrial/evidence?" + query,
        "GET",
        undefined,
        requestSignal(),
      );
      setPreview(await response.json());
    });
  }
  async function create() {
    await action(async () => {
      createId.current ||= crypto.randomUUID();
      const row = await api("POST /industrial/investigations", {
        signal: requestSignal(),
        body: {
          id: createId.current,
          asset_id: asset,
          scenario,
          start: start + ":00Z",
          end: end + ":00Z",
        },
      });
      accept(row);
      setDraft("");
      setBaseline("");
      setEditing(false);
      createId.current = null;
    });
  }
  async function run() {
    if (!selected) return;
    await action(async () => {
      const controller = new AbortController();
      generation.current = controller;
      setGenerating(true);
      // The backend increments the running revision once. Read it before cancel instead of guessing.
      try {
        accept(
          await api("POST /industrial/investigations/{identifier}/generate", {
            params: { identifier: selected.id },
            body: { expected_revision: selected.revision },
            signal: AbortSignal.any([
              controller.signal,
              AbortSignal.timeout(125000),
            ]),
          }),
        );
      } catch (reason) {
        if (!controller.signal.aborted) throw reason;
      } finally {
        generation.current = null;
        setGenerating(false);
      }
    });
  }
  async function cancel() {
    if (
      !selected ||
      cancelPending.current ||
      (pending.current && !generation.current)
    )
      return;
    cancelPending.current = true;
    setCancelling(true);
    setError("");
    setNotice("");
    const signal = requestSignal();
    function stopped(row: InvestigationOut) {
      const value = accept(row);
      generation.current?.abort();
      setNotice(
        value.status === "cancelled"
          ? text(
              "Application operation stopped. Upstream provider computation may continue.",
              "Anwendungsvorgang gestoppt. Der Anbieter kann noch weiterrechnen.",
            )
          : text(
              "Generation has already ended. Saved state loaded.",
              "Die Generierung ist bereits beendet. Der gespeicherte Zustand wurde geladen.",
            ),
      );
    }
    try {
      const row = await api("GET /industrial/investigations/{identifier}", {
        params: { identifier: selected.id },
        signal,
      });
      if (row.status === "running")
        stopped(
          await api("POST /industrial/investigations/{identifier}/cancel", {
            params: { identifier: selected.id },
            body: { expected_revision: row.revision },
            signal,
          }),
        );
      else stopped(row);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "revision_conflict") {
        try {
          // Reconcile a completion race with one read, never another cancel write.
          const current = await api(
            "GET /industrial/investigations/{identifier}",
            {
              params: { identifier: selected.id },
              signal,
            },
          );
          if (current.status !== "running") {
            stopped(current);
            return;
          }
        } catch {
          /* Preserve the original failure and entered work. */
        }
      }
      setError(message(reason));
    } finally {
      cancelPending.current = false;
      setCancelling(false);
    }
  }
  function refresh() {
    if (!selected) return;
    navigate(() => {
      void action(async () => {
        const row = accept(
          await api("GET /industrial/investigations/{identifier}", {
            params: { identifier: selected.id },
            signal: requestSignal(),
          }),
        );
        setDraft(row.payload.draft || "");
        setBaseline(row.payload.draft || "");
        setEditing(Boolean(row.payload.draft));
        setReviewNote("");
      });
    });
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || selected.status !== "completed") return;
    await action(async () => {
      const row = accept(
        await api("PUT /industrial/investigations/{identifier}/draft", {
          signal: requestSignal(),
          params: { identifier: selected.id },
          body: { expected_revision: selected.revision, text: draft },
        }),
      );
      setBaseline(row.payload.draft || "");
      setNotice(
        text(
          "Internal draft saved. Nothing was dispatched.",
          "Interner Entwurf gespeichert. Nichts wurde versendet.",
        ),
      );
    });
  }
  async function review(decision: "accepted" | "needs_changes") {
    if (
      !selected ||
      !reviewNote.trim() ||
      draft !== baseline ||
      draft !== selected.payload.draft
    )
      return;
    await action(async () => {
      accept(
        await api("POST /industrial/investigations/{identifier}/review", {
          signal: requestSignal(),
          params: { identifier: selected.id },
          body: {
            expected_revision: selected.revision,
            note: reviewNote,
            decision,
          },
        }),
      );
      setReviewNote("");
      setNotice(
        text(
          "Owner self-review recorded; this is not independent approval.",
          "Eigene Prüfung aufgezeichnet; keine unabhängige Freigabe.",
        ),
      );
    });
  }
  function exportEvidence() {
    if (!selected || !payload || locked || generating) return;
    const document = {
      format: "onesa-industrial-evidence-v1.1",
      label: "Synthetic demonstration · no connected equipment",
      selection: payload.selection,
      investigation_revision: selected.revision,
      snapshot_sha256: payload.snapshot_sha256,
      fixture_version: payload.evidence.fixture_version,
      metadata_version: payload.evidence.metadata_version,
      facts: payload.facts,
      coverage: payload.coverage,
      sources: payload.evidence.references.map(({ id, version, anchor, sha256, rights }) => ({ id, version, anchor, sha256, rights })),
      explanation: payload.explanation,
      generation: payload.generation && {
        mode: payload.generation.mode, backend: payload.generation.backend,
        model: payload.generation.model, revision: payload.generation.revision,
        input_tokens: payload.generation.input_tokens, output_tokens: payload.generation.output_tokens,
        latency_ms: payload.generation.latency_ms, cost: payload.generation.cost,
      },
      outcome: selected.status,
      draft: payload.draft,
      review: payload.review,
      limitations: ["Citation and quotation matches are not semantic assurance.", "Owner self-review is not independent engineering approval.", "No factory/customer data, dispatch, machine writes or physical operation.", "Costs and comparative benefit have not been established."],
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(document, null, 2)], { type: "application/json" }));
    const link = window.document.createElement("a");
    link.href = url;
    link.download = "onesa-industrial-synthetic-evidence.json";
    link.click();
    URL.revokeObjectURL(url);
    setNotice(text("Synthetic evidence downloaded. Keep it within your approved review scope.", "Synthetische Belege heruntergeladen. Nur im genehmigten Prüfungsumfang verwenden."));
  }
  const facts = payload?.facts || preview?.facts;
  return (
    <FeatureShell title="Industrial Investigation" contentLang={locale}>
      <div className={styles.banner}>
        <span>
          {text(
            "INDUSTRIAL AI · SYNTHETIC DEMONSTRATION",
            "INDUSTRIAL AI · SYNTHETISCHE DEMONSTRATION",
          )}
        </span>
        <p>
          {text(
            "No connected equipment. Investigate evidence, then prepare an internal draft for human review.",
            "Keine verbundenen Anlagen. Untersuche Belege und erstelle einen internen Entwurf zur menschlichen Prüfung.",
          )}
        </p>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <p role="status" aria-live="polite">
        {locked
          ? text(
              "Working… Facts and drafts stay separate from generation.",
              "In Bearbeitung… Fakten und Entwürfe bleiben von der Generierung getrennt.",
            )
          : notice}
      </p>
      <div className={styles.workspace}>
        <nav
          aria-label={text(
            "Saved investigations",
            "Gespeicherte Untersuchungen",
          )}
          className={styles.saved}
        >
          <button disabled={locked} onClick={() => choose(null)}>
            {text("New investigation", "Neue Untersuchung")}
          </button>
          {listState === "loading" && <p role="status">{text("Loading saved investigations…", "Gespeicherte Untersuchungen werden geladen…")}</p>}
          {listState === "failed" && <p role="alert">{text("Saved investigations could not be loaded. Your entries are kept.", "Gespeicherte Untersuchungen konnten nicht geladen werden. Eingaben bleiben erhalten.")}</p>}
          {listState === "loaded" && !items.length && (
            <p>
              {text(
                "No saved investigations.",
                "Keine gespeicherten Untersuchungen.",
              )}
            </p>
          )}
          {items.map((item) => (
            <button
              key={item.id}
              disabled={locked}
              aria-current={selected?.id === item.id ? "true" : undefined}
              onClick={() => choose(item)}
            >
              {item.payload.selection.asset_id}
              <small>
                {item.status} · r{item.revision}
              </small>
            </button>
          ))}
        </nav>
        <div className={styles.content}>
          {!selected && importAvailable && <IndustrialImport locked={locked} accept={accept} />}
          {!selected && (
            <form onSubmit={inspect} className={styles.panel}>
              <h2>{text("1. Select evidence", "1. Belege auswählen")}</h2>
              <fieldset disabled={locked} className={styles.fields}>
                <label>
                  {text("Demo asset", "Demo-Anlage")}
                  <select
                    value={asset}
                    onChange={(e) => {
                      setAsset(e.target.value);
                      setPreview(null);
                      createId.current = null;
                    }}
                  >
                    {assets.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {text("Scenario", "Szenario")}
                  <select
                    value={scenario}
                    onChange={(e) => {
                      setScenario(e.target.value as Scenario);
                      setPreview(null);
                      createId.current = null;
                    }}
                  >
                    {scenarios.map((name) => (
                      <option key={name} value={name}>
                        {name.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {text("Start (UTC, inclusive)", "Beginn (UTC, inklusive)")}
                  <input
                    required
                    type="datetime-local"
                    value={start}
                    onChange={(e) => {
                      setStart(e.target.value);
                      setPreview(null);
                      createId.current = null;
                    }}
                  />
                </label>
                <label>
                  {text("End (UTC, exclusive)", "Ende (UTC, exklusiv)")}
                  <input
                    required
                    type="datetime-local"
                    value={end}
                    onChange={(e) => {
                      setEnd(e.target.value);
                      setPreview(null);
                      createId.current = null;
                    }}
                  />
                </label>
              </fieldset>
              <p>
                {text(
                  "Fixture date: 20 October 2026. Windows are limited to 24 hours. All controls use UTC.",
                  "Fixture-Datum: 20. Oktober 2026. Höchstens 24 Stunden. Alle Zeitangaben in UTC.",
                )}
              </p>
              <div className={styles.actions}>
                <button disabled={locked || !assets.length} type="submit">
                  {text("Review source coverage", "Quellenabdeckung prüfen")}
                </button>
                {preview && (
                  <button disabled={locked} type="button" onClick={create}>
                    {text("Create investigation", "Untersuchung erstellen")}
                  </button>
                )}
              </div>
              {preview && <CoveragePanel info={preview.coverage} de={de} />}
            </form>
          )}
          {selected && (
            <section className={styles.panel}>
              <p className="eyebrow">
                {selected.payload.selection.asset_id} · r{selected.revision} ·{" "}
                {selected.status}
              </p>
              <h2>{text("2. Observed evidence", "2. Beobachtete Belege")}</h2>
              <p>
                {selected.payload.selection.start} →{" "}
                {selected.payload.selection.end}
              </p>
              <CoveragePanel info={selected.payload.coverage} de={de} />
              {importAvailable && <IndustrialFactsTool key={selected.id} investigation={selected} locked={locked} />}
              <button disabled={locked || generating} onClick={exportEvidence}>{text("Download synthetic evidence", "Synthetische Belege herunterladen")}</button>
              <details><summary>{text("Engineering review criteria", "Kriterien für die technische Prüfung")}</summary>
                <p>{text("Check the asset, UTC window, coverage and source versions. Verify each fact and quoted source. Reject unsupported causes, invented certainty or operating instructions. Record missing evidence and useful corrections before accepting a draft.", "Prüfe Anlage, UTC-Zeitfenster, Abdeckung und Quellversionen. Prüfe jeden Fakt und jedes Zitat. Lehne unbelegte Ursachen, erfundene Gewissheit und Betriebsanweisungen ab. Dokumentiere fehlende Belege und Korrekturen vor Annahme eines Entwurfs.")}</p>
                <p>{text("Acceptance records your review of an internal draft. It does not authorize equipment work or establish independent human-domain validation.", "Die Annahme dokumentiert die Prüfung eines internen Entwurfs. Sie genehmigt keine Maschinenarbeit und belegt keine unabhängige fachliche Validierung.")}</p>
              </details>
              <div className={styles.actions}>
                <button
                  disabled={
                    locked ||
                    selected.status === "running" ||
                    Boolean(payload?.draft)
                  }
                  onClick={run}
                >
                  {text("Run investigation", "Untersuchung starten")}
                </button>
                {(generating || selected.status === "running") && (
                  <button
                    disabled={cancelling || (busy && !generating)}
                    onClick={cancel}
                  >
                    {text("Cancel generation", "Generierung abbrechen")}
                  </button>
                )}
                <button disabled={locked} onClick={refresh}>
                  {text("Refresh saved state", "Gespeicherten Zustand laden")}
                </button>
              </div>
              {payload?.error && (
                <p role="alert">
                  {text(
                    "Generation did not complete. Facts remain available:",
                    "Generierung nicht abgeschlossen. Fakten bleiben verfügbar:",
                  )}{" "}
                  {payload.error}
                </p>
              )}
            </section>
          )}
          {facts && (
            <section
              className={styles.panel}
              aria-label={text("Calculated facts", "Berechnete Fakten")}
            >
              <h2>
                {text(
                  "Facts, calculated independently",
                  "Unabhängig berechnete Fakten",
                )}
              </h2>
              <div className={styles.metrics}>
                <div>
                  <strong>{facts.event_count}</strong>
                  <span>{text("stop events", "Stopp-Ereignisse")}</span>
                </div>
                <div>
                  <strong>{facts.known_downtime_seconds / 60}</strong>
                  <span>
                    {text(
                      "known downtime · minutes",
                      "bekannte Stillstandszeit · Minuten",
                    )}
                  </span>
                </div>
                <div>
                  <strong>{facts.distinct_downtime_episodes}</strong>
                  <span>
                    {text("distinct episodes", "getrennte Stillstände")}
                  </span>
                </div>
              </div>
              <p>
                {text(
                  "Cause not established. Overlapping intervals are counted once. No OEE is calculated.",
                  "Ursache nicht festgestellt. Überlappungen werden einmal gezählt. Keine OEE-Berechnung.",
                )}
              </p>
              {!facts.downtime_complete && (
                <p role="note">
                  {text(
                    "Incomplete or poor-quality events: known downtime is a lower bound, not a complete total.",
                    "Unvollständige oder schlechte Daten: bekannte Stillstandszeit ist nur eine Untergrenze.",
                  )}
                </p>
              )}
              <div
                className={styles.table}
                tabIndex={0}
                role="region"
                aria-label={text(
                  "Stop timeline scroll area",
                  "Scrollbereich der Stopp-Zeitachse",
                )}
              >
                <table>
                  <caption>
                    {text("Stop timeline · UTC", "Stopp-Zeitachse · UTC")}
                  </caption>
                  <thead>
                    <tr>
                      <th>{text("Source event", "Quellereignis")}</th>
                      <th>{text("Start", "Beginn")}</th>
                      <th>{text("End", "Ende")}</th>
                      <th>{text("Quality", "Qualität")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {facts.timeline.map((event) => (
                      <tr key={event.id}>
                        <th>{event.id}</th>
                        <td>{event.clipped_start.slice(11, 19)}</td>
                        <td>{event.clipped_end.slice(11, 19)}</td>
                        <td>{event.quality}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!facts.timeline.length && (
                  <p>
                    {text(
                      "No complete stop intervals in this window.",
                      "Keine vollständigen Stopp-Intervalle in diesem Fenster.",
                    )}
                  </p>
                )}
              </div>
            </section>
          )}
          {payload?.explanation && (
            <section className={styles.panel}>
              <h2>
                {text(
                  "3. Hypotheses and limitations",
                  "3. Hypothesen und Grenzen",
                )}
              </h2>
              <p>
                {payload.explanation.abstained
                  ? payload.generation?.mode === "model"
                    ? text(
                        "Model abstained · cause not established",
                        "Modell enthält sich · Ursache nicht festgestellt",
                      )
                    : text(
                        "Abstained before generation",
                        "Vor Generierung enthalten",
                      )
                  : payload.generation?.mode === "mock"
                    ? text(
                        "MOCK · No real model response",
                        "MOCK · Keine echte Modellantwort",
                      )
                    : payload.generation?.mode === "model"
                      ? text(
                          "Model-generated hypotheses · verify the sources",
                          "Modellgenerierte Hypothesen · Quellen prüfen",
                        )
                      : text(
                          "Abstained before generation",
                          "Vor Generierung enthalten",
                        )}
              </p>
              <p>
                {text(
                  "Synthetic reference and generated narrative are currently in English.",
                  "Synthetische Referenzen und generierte Erklärungen sind derzeit auf Englisch.",
                )}
              </p>
              <p>{text("Citations identify source text; they do not establish that a hypothesis is supported. A qualified engineer must review each conclusion before use.", "Zitate bezeichnen Quelltext; sie belegen nicht automatisch eine Hypothese. Fachkundige Prüfung ist vor der Nutzung erforderlich.")}</p>
              {payload.explanation.hypotheses.map((hypothesis, index) => (
                <article key={index}>
                  <h3>
                    {text("Possible explanation", "Mögliche Erklärung")}{" "}
                    {index + 1}
                  </h3>
                  <p lang="en">{hypothesis.statement}</p>
                  <blockquote lang="en">{hypothesis.quote}</blockquote>
                  <p lang="en">{hypothesis.human_review}</p>
                  <ul>
                    {hypothesis.citations.map((citation) => (
                      <li
                        key={
                          citation.document_id +
                          ":" +
                          citation.version +
                          ":" +
                          citation.anchor
                        }
                      >
                        <a
                          href={`#source-${citation.document_id}-${citation.version}-${citation.anchor}`}
                        >
                          {citation.document_id} · v{citation.version} ·{" "}
                          {citation.anchor}
                        </a>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
              <ul>
                {payload.explanation.limitations.map((item) => (
                  <li lang="en" key={item}>{item}</li>
                ))}
              </ul>
              <p>
                {text("Generation latency", "Generierungsdauer")}:{" "}
                {payload.generation?.latency_ms ?? "—"} ms ·{" "}
                {text("Cost", "Kosten")}:{" "}
                {payload.generation?.cost ??
                  text("not observed", "nicht beobachtet")}
              </p>
              {!editing && (
                <button
                  disabled={locked}
                  onClick={() => {
                    setEditing(true);
                    setBaseline(payload.draft || "");
                    setDraft(
                      payload.draft ||
                        text(
                          "Internal investigation draft\nObserved cause: not established.\nHuman review required:\n",
                          "Interner Untersuchungsentwurf\nUrsache: nicht festgestellt.\nMenschliche Prüfung erforderlich:\n",
                        ),
                    );
                  }}
                >
                  {payload.draft
                    ? text("Open saved draft", "Gespeicherten Entwurf öffnen")
                    : text(
                        "Create internal draft",
                        "Internen Entwurf erstellen",
                      )}
                </button>
              )}
            </section>
          )}
          {payload && (
            <section className={styles.panel}>
              <h2>{text("Source provenance", "Quellenherkunft")}</h2>
              <p className={styles.hash}>
                Snapshot SHA-256: {payload.snapshot_sha256}
              </p>
              {payload.evidence.signals.map((signal) => (
                <p key={signal.id}>
                  {signal.id}: {signal.value} {signal.unit} · {signal.timestamp}{" "}
                  · {signal.quality}
                </p>
              ))}
              {payload.evidence.references.map((source) => (
                <details
                  lang="en"
                  key={source.id + source.version}
                  id={`source-${source.id}-${source.version}-${source.anchor}`}
                >
                  <summary>
                    {source.title} · v{source.version} · {source.anchor}
                  </summary>
                  <p>{source.text}</p>
                  <p>{source.rights}</p>
                  <p className={styles.hash}>SHA-256: {source.sha256}</p>
                </details>
              ))}
            </section>
          )}
          {editing && (
            <section className={styles.panel}>
              <h2>
                {text("4. Internal work draft", "4. Interner Arbeitsentwurf")}
              </h2>
              <p>
                {text(
                  "Saved only in your account. No ticket, work order or email is sent. You review your own draft; this is not an independent approval.",
                  "Nur in deinem Konto gespeichert. Kein Ticket, Arbeitsauftrag oder E-Mail-Versand. Eigene Prüfung, keine unabhängige Freigabe.",
                )}
              </p>
              <form onSubmit={save}>
                <label htmlFor="industrial-draft">
                  {text("Draft text", "Entwurfstext")}
                </label>
                <textarea
                  id="industrial-draft"
                  disabled={locked}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={8}
                  maxLength={8000}
                  required
                />
                <button
                  disabled={
                    locked || !draft.trim() || selected?.status !== "completed"
                  }
                >
                  {text("Save internal draft", "Internen Entwurf speichern")}
                </button>
              </form>
              {payload?.draft && (
                <>
                  <label htmlFor="industrial-review-note">
                    {text("Review note", "Prüfnotiz")}
                  </label>
                  <textarea
                    id="industrial-review-note"
                    disabled={locked}
                    value={reviewNote}
                    onChange={(e) => setReviewNote(e.target.value)}
                    rows={3}
                    maxLength={2000}
                  />
                  <div className={styles.actions}>
                    <button
                      disabled={
                        locked ||
                        draft !== baseline ||
                        draft !== payload.draft ||
                        !reviewNote.trim()
                      }
                      onClick={() => review("accepted")}
                    >
                      {text("Record accepted", "Als geprüft aufzeichnen")}
                    </button>
                    <button
                      disabled={
                        locked ||
                        draft !== baseline ||
                        draft !== payload.draft ||
                        !reviewNote.trim()
                      }
                      onClick={() => review("needs_changes")}
                    >
                      {text("Request changes", "Änderungen anfordern")}
                    </button>
                  </div>
                </>
              )}
              {payload?.review && (
                <p role="status">
                  {payload.review.decision} · r
                  {payload.review.reviewed_revision} · {payload.review.scope}
                </p>
              )}
            </section>
          )}
        </div>
      </div>
    </FeatureShell>
  );
}
function CoveragePanel({ info, de }: { info: Coverage; de: boolean }) {
  return (
    <div className={styles.coverage}>
      <h3>{de ? "Abdeckung und Qualität" : "Coverage and quality"}</h3>
      <p>{info.signal_coverage}</p>
      {info.missing.length > 0 && (
        <p>
          {de ? "Fehlend" : "Missing"}: {info.missing.join(", ")}
        </p>
      )}
      {info.stale_signal_ids.length > 0 && (
        <p>
          {de ? "Veraltet" : "Stale"}: {info.stale_signal_ids.join(", ")}
        </p>
      )}
      {info.reference_conflict && (
        <p role="note">
          {de
            ? "Widersprüchliche Referenzen: Autorität klären, bevor eine Schlussfolgerung möglich ist."
            : "Conflicting references: establish the applicable authority before drawing a conclusion."}
        </p>
      )}
    </div>
  );
}
