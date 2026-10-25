"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import RequireSession from "../../../components/require-session";
import FeatureShell from "../../../components/feature-shell";
import TwinSetup from "../../../components/twin-setup";
import TwinInspectionControls, {
  TwinExplosionControls,
} from "../../../components/twin-inspection-controls";
import {
  DEFAULT_INSPECTION,
  inspectionViewSchema,
  type InspectionControls,
} from "../../../lib/twin-viewer-contract";
import {
  twin,
  type Detail,
  type Evidence,
  type History,
  type Model,
  type TwinAsset,
} from "../../../lib/twins";
import styles from "./twins.module.css";

const Viewer = dynamic(() => import("../../../components/twin-viewer"), {
  ssr: false,
  loading: () => <p role="status">Preparing 3D viewer…</p>,
});
type Catalog = {
  assets: TwinAsset[];
  templates: {
    id: string;
    name: string;
    definition: { components: { id: string; name: string }[] };
  }[];
};
const clock = (date: string) =>
  new Date(date).toLocaleString(undefined, { timeZoneName: "short" });

function Workspace() {
  const [catalog, setCatalog] = useState<Catalog>({
      assets: [],
      templates: [],
    }),
    [selectedAsset, setSelectedAsset] = useState(""),
    [detail, setDetail] = useState<Detail | null>(null),
    [selected, setSelected] = useState(""),
    [tab, setTab] = useState("Model"),
    [mode, setMode] = useState("simulated");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loaded, setLoaded] = useState(false),
    [setup, setSetup] = useState(false),
    [connected, setConnected] = useState(true);
  const [hidden, setHidden] = useState<string[]>([]),
    [isolated, setIsolated] = useState<string | null>(null),
    [transparent, setTransparent] = useState(false),
    [focus, setFocus] = useState(0),
    [savedCamera, setSavedCamera] = useState<number[] | null>(null);
  const [inspection, setInspection] = useState<InspectionControls>({
    ...DEFAULT_INSPECTION,
  });
  const camera = useRef<number[]>([3, 2, 4, 0, 0.5, 0]),
    activeMutation = useRef(false);
  const [history, setHistory] = useState<History | null>(null),
    [evidence, setEvidence] = useState<Evidence | null>(null),
    [question, setQuestion] = useState(
      "What should I inspect about this bearing vibration?",
    ),
    [hours, setHours] = useState("1"),
    [sourceToken, setSourceToken] = useState<{
      id: string;
      ingestion_token: string;
    } | null>(null);
  const [readiness, setReadiness] = useState<{
    ready: boolean;
    storage: string;
    model_backend: string;
    simulation_enabled?: boolean;
  } | null>(null);
  const refreshCatalog = useCallback(async () => {
    const result = await twin<Catalog>("/catalog");
    setCatalog(result);
    return result;
  }, []);
  const reload = useCallback(
    async (id?: string) => {
      const result = await refreshCatalog();
      const target = id || selectedAsset || result.assets[0]?.id;
      if (target) {
        setSelectedAsset(target);
        setDetail(await twin<Detail>(`/assets/${target}?mode=${mode}`));
      }
    },
    [refreshCatalog, selectedAsset, mode],
  );
  const run = useCallback((action: () => Promise<void>) => {
    if (activeMutation.current) return;
    activeMutation.current = true;
    setBusy(true);
    setError("");
    action()
      .catch((reason) => setError((reason as Error).message))
      .finally(() => {
        activeMutation.current = false;
        setBusy(false);
      });
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      twin<Catalog>("/catalog", "GET", undefined, controller.signal),
      twin<{
        ready: boolean;
        storage: string;
        model_backend: string;
        simulation_enabled: boolean;
      }>("/readiness", "GET", undefined, controller.signal),
    ])
      .then(([result, status]) => {
        setCatalog(result);
        setReadiness(status);
        setSelectedAsset(result.assets[0]?.id || "");
        setSetup(!result.assets.length);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError((reason as Error).message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoaded(true);
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!selectedAsset) return;
    const controller = new AbortController();
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const value = await twin<Detail>(
          `/assets/${selectedAsset}?mode=${mode}`,
          "GET",
          undefined,
          AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]),
        );
        if (alive) {
          setDetail(value);
          setConnected(true);
        }
      } catch {
        if (alive) {
          setConnected(false);
        }
      } finally {
        if (alive) timer = setTimeout(poll, 5000);
      }
    }
    poll();
    return () => {
      alive = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [selectedAsset, mode]);
  const safeDetail = detail?.asset.id === selectedAsset ? detail : null;
  const asset = safeDetail?.asset || null;
  const component =
    asset?.definition.components.find((c) => c.id === selected) ||
    asset?.definition.components[0];
  const selectedId = component?.id || "";
  const modelJSON = JSON.stringify(
    safeDetail?.models.find(
      (m) =>
        m.id === (asset?.active_model_id || asset?.definition.review_model_id),
    ) || null,
  );
  const model = useMemo<Model | null>(() => JSON.parse(modelJSON), [modelJSON]);
  const componentJSON = JSON.stringify(asset?.definition.components || []);
  const components = useMemo<TwinAsset["definition"]["components"]>(
    () => JSON.parse(componentJSON),
    [componentJSON],
  );
  const onCamera = useCallback((value: number[]) => {
    camera.current = value;
  }, []);
  const onSelect = useCallback((id: string) => {
    setSelected(id);
    setEvidence(null);
  }, []);
  function chooseAsset(id: string) {
    setSelectedAsset(id);
    setDetail(null);
    setSelected("");
    setHistory(null);
    setEvidence(null);
    setHidden([]);
    setIsolated(null);
    setSavedCamera(null);
    setSourceToken(null);
    setInspection({ ...DEFAULT_INSPECTION });
    setTransparent(false);
  }
  function timeWindow() {
    return {
      start: new Date(Date.now() - Number(hours) * 3600000).toISOString(),
      end: new Date().toISOString(),
      mode,
    };
  }
  const signals =
    safeDetail?.state.filter((s) => s.binding.component_id === selectedId) ||
    [];
  return (
    <FeatureShell title="Digital Twins" wide>
      <div className={styles.workspace}>
        <div className={styles.topline}>
          <p>Industrial AI / Digital Twins</p>
          <button onClick={() => setSetup((v) => !v)} aria-expanded={setup}>
            {setup ? "Close setup" : "Equipment setup"}
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {!loaded && <p role="status">Loading your equipment workspace…</p>}
        {loaded && !readiness?.ready && (
          <p role="status">
            Private durable model storage is not ready. Equipment information
            remains available; configure the scoped storage adapter before
            importing models.
          </p>
        )}
        <fieldset disabled={busy} className={styles.controls}>
          <legend className={styles.sr}>Equipment workspace controls</legend>
          <label>
            Equipment
            <select
              aria-label="Equipment"
              value={selectedAsset}
              onChange={(e) => chooseAsset(e.target.value)}
            >
              <option value="">Choose equipment</option>
              {catalog.assets.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} · {a.serial}
                </option>
              ))}
            </select>
          </label>
          <label>
            Data mode
            <select
              aria-label="Data mode"
              value={mode}
              onChange={(e) => {
                setMode(e.target.value);
                setHistory(null);
                setEvidence(null);
              }}
            >
              <option value="simulated">Simulated</option>
              <option value="live">Live</option>
              <option value="replay">Recorded replay</option>
            </select>
          </label>
          <p role="status">
            {busy
              ? "Saving…"
              : !connected
                ? "Platform disconnected · last observations retained"
                : mode === "replay"
                  ? "Replay · live state and alarms are unchanged"
                  : `${mode === "simulated" ? "Simulated" : "Live"} data · resynchronizes every 5 seconds`}
          </p>
        </fieldset>
        {loaded && catalog.assets.length === 0 && (
          <section className={styles.empty}>
            <h2>Your equipment workspace</h2>
            <p>
              Create equipment or import an AAS package. For an isolated
              development demonstration, explicitly load two illustrative pumps;
              no customer records or physical equipment are connected.
            </p>
            <button
              disabled={busy || !readiness?.ready}
              onClick={() =>
                run(async () => {
                  const result = await twin<{ assets: { id: string }[] }>(
                    "/demo",
                    "POST",
                  );
                  await reload(result.assets[0]?.id);
                  setSetup(false);
                })
              }
            >
              Load isolated pump demonstration
            </button>
            <p>
              The demonstration endpoint is disabled unless the isolated pilot
              is explicitly configured.
            </p>
          </section>
        )}
        {setup && (
          <fieldset disabled={busy} className={styles.setup}>
            <TwinSetup
              asset={asset}
              templates={catalog.templates}
              models={safeDetail?.models || []}
              onSaved={reload}
              run={run}
              Viewer={Viewer}
            />
          </fieldset>
        )}
        {asset && (
          <>
            <div
              className={styles.tabs}
              role="tablist"
              aria-label="Equipment views"
            >
              {["Model", "Details", "History", "Documents"].map((name) => (
                <button
                  key={name}
                  id={`tab-${name}`}
                  role="tab"
                  aria-selected={tab === name}
                  aria-controls={`panel-${name}`}
                  tabIndex={tab === name ? 0 : -1}
                  onClick={() => setTab(name)}
                  onKeyDown={(event) => {
                    if (
                      ["ArrowLeft", "ArrowRight", "Home", "End"].includes(
                        event.key,
                      )
                    ) {
                      event.preventDefault();
                      const names = [
                          "Model",
                          "Details",
                          "History",
                          "Documents",
                        ],
                        next =
                          event.key === "Home"
                            ? 0
                            : event.key === "End"
                              ? 3
                              : (names.indexOf(tab) +
                                  (event.key === "ArrowRight" ? 1 : 3)) %
                                4;
                      setTab(names[next]);
                      document.getElementById(`tab-${names[next]}`)?.focus();
                    }
                  }}
                >
                  {name}
                </button>
              ))}
            </div>
            <div className={styles.assembly}>
              <aside className={styles.tree} aria-label="Equipment components">
                <h2>{asset.name}</h2>
                <p>{asset.serial}</p>
                {readiness?.simulation_enabled &&
                  asset.definition.reference_version !== "2.0.0" && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          const result = await twin<{
                            assets: { id: string }[];
                          }>("/demo", "POST");
                          chooseAsset(result.assets[0].id);
                          await reload(result.assets[0].id);
                        })
                      }
                    >
                      Add detailed reference
                    </button>
                  )}
                <details open className={styles.bom}>
                  <summary>Assembly / BOM · {components.length} items</summary>
                  <ul>
                    {components.map((c) => (
                      <li key={c.id}>
                        <button
                          aria-pressed={selectedId === c.id}
                          onClick={() => onSelect(c.id)}
                          style={{ paddingInlineStart: c.parent_id ? 22 : 12 }}
                          title={[c.inventory, c.material, c.inventory_note]
                            .filter(Boolean)
                            .join(" · ")}
                        >
                          {c.name}
                          {hidden.includes(c.id) ? " · hidden" : ""}
                        </button>
                      </li>
                    ))}
                  </ul>
                </details>
                <p>
                  {asset.definition.stage === "active"
                    ? "Reviewed workspace active"
                    : `Setup: ${asset.definition.stage}`}
                </p>
              </aside>
              <section
                role="tabpanel"
                id="panel-Model"
                aria-labelledby="tab-Model"
                hidden={tab !== "Model"}
                className={styles.modelPanel}
              >
                <div className={styles.toolbar}>
                  <button
                    onClick={() => {
                      setSavedCamera(null);
                      setFocus((v) => Math.abs(v) + 1);
                    }}
                  >
                    Focus selected
                  </button>
                  <button
                    onClick={() => {
                      setSavedCamera(null);
                      setFocus((v) => -Math.abs(v) - 1);
                      setHidden([]);
                      setIsolated(null);
                    }}
                  >
                    Reset view
                  </button>
                  <button
                    aria-pressed={isolated === selectedId}
                    onClick={() =>
                      setIsolated((value) =>
                        value === selectedId ? null : selectedId,
                      )
                    }
                  >
                    Isolate
                  </button>
                  <button
                    aria-pressed={hidden.includes(selectedId)}
                    onClick={() =>
                      setHidden((value) =>
                        value.includes(selectedId)
                          ? value.filter((id) => id !== selectedId)
                          : [...value, selectedId],
                      )
                    }
                  >
                    {hidden.includes(selectedId)
                      ? "Show selected"
                      : "Hide selected"}
                  </button>
                  <button
                    aria-pressed={transparent}
                    onClick={() => setTransparent((v) => !v)}
                  >
                    Transparent surroundings
                  </button>
                  <button
                    disabled={busy || !model}
                    onClick={() =>
                      run(async () => {
                        await twin(`/assets/${asset.id}/notes`, "POST", {
                          kind: "viewpoint",
                          component_id: selectedId,
                          camera: camera.current,
                          model_revision_id: model?.id,
                          inspection_view: {
                            ...inspection,
                            hidden_component_ids: hidden,
                            isolated_component_id: isolated,
                            transparent_surroundings: transparent,
                          },
                          text: "Saved equipment view",
                        });
                        await reload(asset.id);
                      })
                    }
                  >
                    Save viewpoint
                  </button>
                </div>
                {model?.definition.inspection && (
                  <TwinExplosionControls
                    value={inspection}
                    onChange={setInspection}
                  />
                )}
                <div className={styles.viewport}>
                  {model ? (
                    <Viewer
                      key={model.id}
                      model={model}
                      assetId={asset.id}
                      signals={safeDetail?.state || []}
                      annotations={safeDetail?.notes || []}
                      components={components}
                      selected={selectedId}
                      onSelect={onSelect}
                      hidden={hidden}
                      isolated={isolated}
                      transparent={transparent}
                      inspection={inspection}
                      focus={focus}
                      camera={savedCamera}
                      onCamera={onCamera}
                    />
                  ) : (
                    <p>
                      No reviewed viewing model. Attach a prepared GLB in
                      Equipment setup. Equipment details and documents remain
                      available.
                    </p>
                  )}
                </div>
                {model && (
                  <TwinInspectionControls
                    model={model}
                    components={components}
                    selected={selectedId}
                    value={inspection}
                    onChange={setInspection}
                    hideCovers={() =>
                      setHidden((current) => [
                        ...new Set([
                          ...current,
                          ...(
                            model.definition.inspection?.cover_components || []
                          )
                            .map(
                              (id) =>
                                components.find(
                                  (c) => c.template_component_id === id,
                                )?.id,
                            )
                            .filter((id): id is string => Boolean(id)),
                        ]),
                      ])
                    }
                    restore={() => {
                      setHidden([]);
                      setIsolated(null);
                      setTransparent(false);
                      setSavedCamera(null);
                      setFocus((v) => -Math.abs(v) - 1);
                    }}
                  />
                )}
                {model && (
                  <p className={styles.caption}>
                    Illustrative geometry where stated by its source. Units:{" "}
                    {model.definition.unit} · {model.definition.frame}. Orbit:
                    drag; pan: right-drag or two fingers; zoom: wheel or pinch.
                    Component selection also works from the list.
                  </p>
                )}
                <div className={styles.toolbar}>
                  {safeDetail?.notes
                    .filter((n) => n.kind === "viewpoint")
                    .map((note, i) => (
                      <button
                        key={note.id}
                        disabled={Boolean(
                          note.payload.model_revision_id &&
                          note.payload.model_revision_id !== model?.id,
                        )}
                        title={
                          note.payload.model_revision_id &&
                          note.payload.model_revision_id !== model?.id
                            ? "Saved against a different model revision; retained for inspection"
                            : undefined
                        }
                        onClick={() => {
                          const saved = note.payload.inspection_view;
                          if (saved) {
                            const controls = Object.fromEntries(
                              Object.keys(DEFAULT_INSPECTION).map((key) => [
                                key,
                                saved[key as keyof typeof saved],
                              ]),
                            );
                            const result = inspectionViewSchema.safeParse(
                              controls,
                              { jitless: true },
                            );
                            if (!result.success) {
                              setError("Saved inspection controls are invalid");
                              return;
                            }
                            setInspection(result.data);
                            setHidden(saved.hidden_component_ids || []);
                            setIsolated(saved.isolated_component_id || null);
                            setTransparent(
                              Boolean(saved.transparent_surroundings),
                            );
                          }
                          onSelect(note.component_id);
                          setSavedCamera(note.payload.camera || null);
                          setFocus((v) => Math.abs(v) + 1);
                        }}
                      >
                        Viewpoint {i + 1}
                      </button>
                    ))}
                </div>
              </section>
              <section
                role="tabpanel"
                id="panel-Details"
                aria-labelledby="tab-Details"
                hidden={tab !== "Details" && tab !== "Model"}
                className={styles.details}
              >
                <h2>{component?.name}</h2>
                <dl>
                  <dt>BOM designation</dt>
                  <dd>
                    {component?.inventory || "part"} ·{" "}
                    {component?.renderable === false
                      ? "selectable assembly of children"
                      : "selectable geometry"}
                  </dd>
                  {component?.material && (
                    <>
                      <dt>Material appearance</dt>
                      <dd>{component.material}</dd>
                    </>
                  )}
                  {component?.inventory_note && (
                    <>
                      <dt>Reference detail</dt>
                      <dd>{component.inventory_note}</dd>
                    </>
                  )}
                  <dt>Equipment</dt>
                  <dd>{asset.name}</dd>
                  <dt>Serial</dt>
                  <dd>{asset.serial}</dd>
                  <dt>Data mode</dt>
                  <dd>{mode}</dd>
                  <dt>Component identifier</dt>
                  <dd>
                    <code>{selectedId}</code>
                  </dd>
                </dl>
                {signals.length === 0 && (
                  <p>
                    No bound measurements in this mode. Connect a source below;
                    a missing value is unknown.
                  </p>
                )}
                {signals.map((signal) => (
                  <div
                    key={signal.source_id + signal.binding.tag}
                    className={styles.signal}
                  >
                    <h3>{signal.binding.metric}</h3>
                    <p>
                      <strong>
                        {signal.reading
                          ? `${signal.reading.value.toLocaleString()} ${signal.reading.unit}`
                          : "Unknown"}
                      </strong>{" "}
                      · {signal.freshness} · {signal.connection}
                    </p>
                    <p>
                      {signal.reading
                        ? `Observed ${clock(signal.reading.observed_at)} · quality ${signal.reading.quality}`
                        : "No observation received"}
                    </p>
                    <p>
                      Source: {signal.source_name}
                      {signal.binding.high !== null
                        ? ` · high rule ${signal.binding.high} ${signal.binding.unit}, hysteresis ${signal.binding.hysteresis}`
                        : ""}
                    </p>
                  </div>
                ))}
                <details>
                  <summary>Relationships and model provenance</summary>
                  <ul>
                    {asset.definition.relationships.map((r, i) => (
                      <li key={i}>
                        {components.find((c) => c.id === r.source)?.name}{" "}
                        {r.kind.replaceAll("_", " ")}{" "}
                        {components.find((c) => c.id === r.target)?.name}
                      </li>
                    ))}
                  </ul>
                  <p>
                    {model?.definition.provenance ||
                      "No model provenance available"}
                  </p>
                  <p>
                    Visualization is not collision geometry, calibrated
                    kinematics or a planning environment.
                  </p>
                </details>
                <details>
                  <summary>Component annotations</summary>
                  {safeDetail?.notes
                    .filter(
                      (n) =>
                        n.kind === "annotation" &&
                        n.component_id === selectedId,
                    )
                    .map((n) => (
                      <p key={n.id}>{n.payload.text}</p>
                    ))}
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      const form = event.currentTarget,
                        data = new FormData(form);
                      run(async () => {
                        await twin(`/assets/${asset.id}/notes`, "POST", {
                          kind: "annotation",
                          component_id: selectedId,
                          text: data.get("text"),
                        });
                        form.reset();
                        await reload(asset.id);
                      });
                    }}
                  >
                    <label>
                      Inspection annotation
                      <textarea name="text" required maxLength={2000} />
                    </label>
                    <button disabled={busy}>Save annotation</button>
                  </form>
                </details>
              </section>
              <section
                role="tabpanel"
                id="panel-History"
                aria-labelledby="tab-History"
                hidden={tab !== "History"}
                className={styles.history}
              >
                <h2>History and rule events</h2>
                <p>
                  Reading history never changes live state. Replay has its own
                  dataset and does not trigger live alarms.
                </p>
                <label>
                  Time range
                  <select
                    value={hours}
                    onChange={(e) => setHours(e.target.value)}
                  >
                    <option value="1">Last hour</option>
                    <option value="24">Last 24 hours</option>
                    <option value="168">Last 7 days</option>
                  </select>
                </label>
                <button
                  disabled={busy}
                  onClick={() =>
                    run(async () =>
                      setHistory(
                        await twin<History>(
                          `/assets/${asset.id}/history`,
                          "POST",
                          timeWindow(),
                        ),
                      ),
                    )
                  }
                >
                  Load history
                </button>
                {history && (
                  <>
                    <p>
                      {clock(history.start)} – {clock(history.end)} ·{" "}
                      {history.mode}
                      {history.truncated
                        ? " · bounded result truncated; narrow the time range"
                        : ""}
                    </p>
                    <h3>Events</h3>
                    {history.events.length ? (
                      <ul>
                        {history.events.map((event) => (
                          <li key={event.id}>
                            <button
                              onClick={() => {
                                onSelect(event.component_id);
                                setTab("Details");
                              }}
                            >
                              {event.kind.replaceAll("_", " ")} · {event.value}{" "}
                              {event.unit} · {clock(event.observed_at)}
                            </button>
                            <p>{event.meaning}</p>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p>No rule events in this window.</p>
                    )}
                    <h3>Observations</h3>
                    <div className={styles.table}>
                      <table>
                        <caption>
                          Bounded {history.mode} reading history
                        </caption>
                        <thead>
                          <tr>
                            <th>Observed</th>
                            <th>Component / tag</th>
                            <th>Value</th>
                            <th>Quality</th>
                          </tr>
                        </thead>
                        <tbody>
                          {history.readings.map((r) => (
                            <tr key={r.id}>
                              <td>{clock(r.observed_at)}</td>
                              <td>
                                {
                                  components.find(
                                    (c) => c.id === r.component_id,
                                  )?.name
                                }{" "}
                                / {r.tag}
                              </td>
                              <td>
                                {r.value} {r.unit}
                              </td>
                              <td>{r.quality}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </section>
              <section
                role="tabpanel"
                id="panel-Documents"
                aria-labelledby="tab-Documents"
                hidden={tab !== "Documents"}
                className={styles.documents}
              >
                <h2>Equipment documents</h2>
                {safeDetail?.documents.length ? (
                  safeDetail.documents.map((doc) => (
                    <Document
                      key={doc.document_id}
                      id={doc.document_id}
                      title={doc.title}
                    />
                  ))
                ) : (
                  <p>
                    No linked manual. Upload TXT/PDF in Equipment setup or link
                    an existing Knowledge document.
                  </p>
                )}
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    const data = new FormData(event.currentTarget);
                    run(async () => {
                      await twin(`/assets/${asset.id}/documents`, "POST", {
                        document_id: data.get("document"),
                        component_id: selectedId,
                      });
                      await reload(asset.id);
                    });
                  }}
                >
                  <label>
                    Existing Knowledge document ID
                    <input name="document" required />
                  </label>
                  <button disabled={busy}>Link to selected component</button>
                </form>
                {asset.definition.source_import_id && (
                  <a
                    href={`/api/v1/twins/files/${asset.definition.source_import_id}/content`}
                  >
                    Download preserved source package
                  </a>
                )}
                {safeDetail?.files.map((file) => (
                  <div key={file.id}>
                    <a href={`/api/v1/twins/files/${file.id}/content`}>
                      Preserved attachment: {file.filename}
                    </a>
                    {/\.(txt|pdf)$/i.test(file.filename) && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          run(async () => {
                            await twin(
                              `/assets/${asset.id}/files/${file.id}/index-document`,
                              "POST",
                              undefined,
                              AbortSignal.timeout(90000),
                            );
                            await reload(asset.id);
                          })
                        }
                      >
                        Index and link {file.filename}
                      </button>
                    )}
                  </div>
                ))}
              </section>
            </div>
            {readiness?.simulation_enabled && (
              <section
                className={styles.toolbar}
                aria-label="Onesa local simulator"
              >
                <p>Onesa local simulated vibration · {component?.name}</p>
                {["cycle", "normal", "alarm", "recovery", "disconnect"].map(
                  (scenario) => (
                    <button
                      key={scenario}
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await twin(`/assets/${asset.id}/simulate`, "POST", {
                            component_id: selectedId,
                            scenario,
                          });
                          await reload(asset.id);
                        })
                      }
                    >
                      {scenario === "cycle"
                        ? "Run local simulated cycle"
                        : scenario === "disconnect"
                          ? "Pause local simulated source"
                          : `Simulate ${scenario}`}
                    </button>
                  ),
                )}
              </section>
            )}
            <div className={styles.investigation}>
              <section>
                <h2>Equipment assistant</h2>
                <p>
                  Uses scoped measurements and associated Knowledge documents.
                  Facts, threshold rules and unconfirmed hypotheses stay
                  distinct.
                </p>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    run(async () =>
                      setEvidence(
                        await twin<Evidence>(
                          `/assets/${asset.id}/tools/evidence`,
                          "POST",
                          {
                            ...timeWindow(),
                            component_id: selectedId,
                            question,
                            use_model:
                              new FormData(event.currentTarget).get("model") ===
                              "on",
                          },
                        ),
                      ),
                    );
                  }}
                >
                  <label>
                    Question about {component?.name}
                    <textarea
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      maxLength={2000}
                      required
                    />
                  </label>
                  <label>
                    <input type="checkbox" name="model" />
                    Request configured model commentary (
                    {readiness?.model_backend || "unknown"})
                  </label>
                  <button disabled={busy}>Inspect selected evidence</button>
                </form>
                {evidence && (
                  <div aria-label="Equipment evidence answer">
                    <p>
                      <strong>
                        {evidence.equipment.name} · {evidence.equipment.serial}{" "}
                        · {evidence.component.name}
                      </strong>
                    </p>
                    <p>{evidence.assistant.status.replaceAll("_", " ")}</p>
                    <p>{evidence.assistant.text}</p>
                    <p>
                      {clock(evidence.history.start)} –{" "}
                      {clock(evidence.history.end)} · {evidence.history.mode}
                    </p>
                    <h3>Observed facts</h3>
                    {evidence.facts.length ? (
                      evidence.facts.map((f) => (
                        <p key={f.source_id + f.binding.tag}>
                          {f.binding.metric}:{" "}
                          {f.reading
                            ? `${f.reading.value} ${f.reading.unit} at ${clock(f.reading.observed_at)}`
                            : "unknown"}{" "}
                          · {f.freshness}
                        </p>
                      ))
                    ) : (
                      <p>No bound readings for this component and mode.</p>
                    )}
                    <h3>Rule outputs</h3>
                    <p>
                      {evidence.history.events.length} threshold events in the
                      bounded window. Cause is not established.
                    </p>
                    {evidence.assistant.hypotheses.map((h, i) => (
                      <div key={i}>
                        <h3>Unconfirmed hypothesis</h3>
                        <p>{h.statement}</p>
                        <blockquote>{h.quote}</blockquote>
                      </div>
                    ))}
                    <h3>Procedure evidence</h3>
                    {evidence.documents.length ? (
                      evidence.documents.map((d) => (
                        <details key={d.document_id + d.chunk}>
                          <summary>
                            {d.title} · section/chunk {d.chunk + 1}
                          </summary>
                          <p>{d.text}</p>
                        </details>
                      ))
                    ) : (
                      <p>
                        No matching associated procedure retrieved. Link a
                        manual and refine the question.
                      </p>
                    )}
                    <p>{evidence.next_inspection}</p>
                    <ul>
                      {evidence.limitations.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                    <button
                      onClick={() =>
                        run(async () => {
                          const action = await twin<{
                            component_ids: string[];
                          }>(
                            `/assets/${asset.id}/viewer-actions`,
                            "POST",
                            evidence.viewer_actions[0],
                          );
                          onSelect(action.component_ids[0]);
                          setSavedCamera(null);
                          setFocus((v) => Math.abs(v) + 1);
                          setTab("Model");
                        })
                      }
                    >
                      Focus evidence component
                    </button>
                  </div>
                )}
                <button
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await twin(`/assets/${asset.id}/inspections`, "POST", {
                        ...timeWindow(),
                        component_id: selectedId,
                        question,
                        use_model: false,
                      });
                      await reload(asset.id);
                    })
                  }
                >
                  Save evidence-backed inspection checklist
                </button>
                {safeDetail?.notes
                  .filter((n) => n.kind === "inspection")
                  .map((n) => (
                    <details key={n.id}>
                      <summary>
                        {n.payload.title} · {clock(n.created_at)}
                      </summary>
                      <p>
                        Saved evidence snapshot ·{" "}
                        {n.payload.evidence?.component.name}
                      </p>
                      <ul>
                        {n.payload.checklist?.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                      <p>{n.payload.evidence?.assistant.text}</p>
                      {n.snapshot_url && (
                        <a
                          href={n.snapshot_url}
                          download={`inspection-${n.id}.json`}
                        >
                          Download complete saved evidence
                        </a>
                      )}
                      {n.payload.evidence?.documents.map((d) => (
                        <p key={d.document_id + d.chunk}>
                          {d.title} · chunk {d.chunk + 1}: {d.text}
                        </p>
                      ))}
                    </details>
                  ))}
              </section>
              <section>
                <details>
                  <summary>Connect read-only measurements</summary>
                  <p>
                    Create a source credential for this equipment. Put it in the
                    private edge adapter configuration. It grants ingestion
                    only. Browser clients never connect to a PLC.
                  </p>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      const data = new FormData(event.currentTarget);
                      run(async () => {
                        const result = await twin<{
                          id: string;
                          ingestion_token: string;
                        }>(`/assets/${asset.id}/sources`, "POST", {
                          name: data.get("name"),
                          mode: data.get("mode"),
                          bindings: [
                            {
                              tag: data.get("tag"),
                              component_id: selectedId,
                              metric: data.get("metric"),
                              unit: data.get("unit"),
                              sample_seconds: 1,
                              stale_seconds: Number(data.get("stale")),
                              high: data.get("high")
                                ? Number(data.get("high"))
                                : null,
                              hysteresis: Number(data.get("hysteresis")),
                            },
                          ],
                        });
                        setSourceToken(result);
                        await reload(asset.id);
                      });
                    }}
                  >
                    <label>
                      Source name
                      <input
                        name="name"
                        required
                        defaultValue="Read-only MQTT source"
                        maxLength={120}
                      />
                    </label>
                    <label>
                      Dataset
                      <select name="mode">
                        <option value="simulated">Simulated fixture</option>
                        <option value="live">Live source</option>
                      </select>
                    </label>
                    <label>
                      Tag
                      <input name="tag" required defaultValue="vibration" />
                    </label>
                    <label>
                      Metric
                      <select name="metric">
                        <option value="vibration">Vibration</option>
                        <option value="temperature">Temperature</option>
                        <option value="pressure">Pressure</option>
                        <option value="rpm">Rotational speed</option>
                        <option value="power">Power</option>
                        <option value="humidity">Humidity</option>
                      </select>
                    </label>
                    <label>
                      Engineering unit
                      <select name="unit">
                        {[
                          "mm/s",
                          "m/s",
                          "Cel",
                          "K",
                          "bar",
                          "Pa",
                          "rpm",
                          "W",
                          "%",
                        ].map((u) => (
                          <option key={u}>{u}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Stale after seconds
                      <input
                        name="stale"
                        type="number"
                        min={2}
                        max={604800}
                        defaultValue={15}
                        required
                      />
                    </label>
                    <label>
                      High threshold (optional)
                      <input
                        name="high"
                        type="number"
                        step="any"
                        defaultValue={5}
                      />
                    </label>
                    <label>
                      Recovery hysteresis
                      <input
                        name="hysteresis"
                        type="number"
                        min={0}
                        step="any"
                        defaultValue={1}
                        required
                      />
                    </label>
                    <button disabled={busy}>
                      Create scoped ingestion source
                    </button>
                  </form>
                  {sourceToken && (
                    <div>
                      <p>
                        New source ID: <code>{sourceToken.id}</code>
                      </p>
                      <label>
                        One-time ingestion credential
                        <input
                          type="password"
                          readOnly
                          autoComplete="off"
                          value={sourceToken.ingestion_token}
                        />
                      </label>
                      <button
                        onClick={() =>
                          run(async () =>
                            navigator.clipboard.writeText(
                              sourceToken.ingestion_token,
                            ),
                          )
                        }
                      >
                        Copy credential to private edge configuration
                      </button>
                      <button onClick={() => setSourceToken(null)}>
                        Dismiss credential
                      </button>
                    </div>
                  )}
                  {safeDetail?.sources.map((s) => (
                    <p key={s.id}>
                      {s.name} · {s.revoked ? "revoked" : "enabled"}
                      {!s.revoked && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            run(async () => {
                              await twin(`/sources/${s.id}`, "DELETE");
                              await reload(asset.id);
                            })
                          }
                        >
                          Revoke source
                        </button>
                      )}
                    </p>
                  ))}
                </details>
              </section>
            </div>
          </>
        )}
      </div>
    </FeatureShell>
  );
}

function Document({ id, title }: { id: string; title: string }) {
  const [text, setText] = useState(""),
    [error, setError] = useState("");
  return (
    <details
      onToggle={async (event) => {
        if (event.currentTarget.open && !text) {
          try {
            const response = await fetch(`/api/v1/knowledge/documents/${id}`, {
              credentials: "same-origin",
              cache: "no-store",
            });
            if (!response.ok)
              throw new Error("Document unavailable or access expired");
            const result = await response.json();
            setText(result.text);
          } catch (reason) {
            setError((reason as Error).message);
          }
        }
      }}
    >
      <summary>{title}</summary>
      {error && <p role="alert">{error}</p>}
      <pre>{text || "Loading associated procedure…"}</pre>
      <Link href="/knowledge">Open Knowledge workspace</Link>
    </details>
  );
}

export default function Page() {
  return (
    <RequireSession title="Digital Twins" destination="/industrial/twins">
      <Workspace />
    </RequireSession>
  );
}
