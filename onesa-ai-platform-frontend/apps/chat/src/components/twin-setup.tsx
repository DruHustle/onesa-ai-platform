"use client";
import { useState } from "react";
import {
  twin,
  uploadTwin,
  type TwinAsset,
  type FilePreview,
  type Model,
} from "../lib/twins";
import type { ComponentType } from "react";

type Template = {
  id: string;
  name: string;
  definition: {
    components: { id: string; name: string; renderable?: boolean }[];
  };
};
export default function TwinSetup({
  asset,
  templates,
  models,
  onSaved,
  run,
  Viewer,
}: {
  asset: TwinAsset | null;
  templates: Template[];
  models: Model[];
  onSaved: (id?: string) => Promise<void>;
  run: (action: () => Promise<void>) => void;
  Viewer: ComponentType<{
    model: Model;
    components: TwinAsset["definition"]["components"];
    selected: string;
    onSelect: (id: string) => void;
    hidden: string[];
    isolated: string | null;
    transparent: boolean;
    focus: number;
    camera: number[] | null;
    onCamera: (v: number[]) => void;
  }>;
}) {
  const [preview, setPreview] = useState<FilePreview | null>(null),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [templateId, setTemplateId] = useState(templates[0]?.id || ""),
    [unit, setUnit] = useState("m");
  const template = templates.find(
    (t) => t.id === (asset?.template_id || templateId),
  );
  const [reviewScale, setReviewScale] = useState(false);
  const draftModel: Model | null =
    preview?.details.format === "glb"
      ? {
          id: preview.id,
          file_id: preview.id,
          template_id: template?.id || "",
          definition: {
            mappings: Object.entries(mapping).map(([node, component_id]) => ({
              node,
              component_id,
            })),
            nodes: preview.details.nodes || [],
            unit,
            meters_per_unit: unit === "mm" ? 0.001 : unit === "cm" ? 0.01 : 1,
            frame: "right-handed-y-up",
            transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            provenance:
              "Uploaded source; review scale and mappings before activation",
            sha256: preview.sha256,
            byte_length: preview.size,
          },
        }
      : null;
  return (
    <section aria-label="Equipment setup">
      <h2>Equipment setup</h2>
      <p>
        Create or import equipment, review its model and mapping, link a manual,
        map signals, then preview and activate.
      </p>
      <details>
        <summary>Create a reusable equipment template</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            run(async () => {
              const names = String(data.get("components"))
                .split(",")
                .map((n) => n.trim())
                .filter(Boolean);
              const result = await twin<{ id: string }>("/templates", "POST", {
                name: data.get("name"),
                kind: data.get("kind"),
                components: names.map((name) => ({
                  id: crypto.randomUUID(),
                  name,
                })),
              });
              setTemplateId(result.id);
              await onSaved();
            });
          }}
        >
          <label>
            Template name
            <input
              name="name"
              required
              maxLength={120}
              placeholder="Pump and motor assembly"
            />
          </label>
          <label>
            Equipment type
            <input
              name="kind"
              required
              maxLength={80}
              placeholder="Centrifugal pump"
            />
          </label>
          <label>
            Component names, separated by commas
            <input
              name="components"
              required
              placeholder="Casing, Motor, Coupling, Bearing, Impeller"
            />
          </label>
          <button>Create template</button>
        </form>
      </details>
      <details open={!asset}>
        <summary>Create an installed equipment instance</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            run(async () => {
              const result = await twin<{ id: string }>("/assets", "POST", {
                template_id: data.get("template"),
                name: data.get("name"),
                serial: data.get("serial"),
                external_id: data.get("external") || "",
              });
              await onSaved(result.id);
            });
          }}
        >
          <label>
            Template
            <select
              name="template"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              required
            >
              <option value="">Choose a template</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Equipment name
            <input name="name" required maxLength={120} />
          </label>
          <label>
            Installed serial number
            <input name="serial" required maxLength={120} />
          </label>
          <label>
            External asset identifier (optional)
            <input name="external" maxLength={200} />
          </label>
          <button disabled={!templateId}>Create equipment</button>
        </form>
      </details>
      <label>
        Attach a model, AAS package or source document
        <input
          type="file"
          accept=".glb,.aasx,.json,.txt,.pdf,.step,.stp,.png,.jpg"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setPreview(null);
            setMapping({});
            setReviewScale(false);
            run(async () => setPreview(await uploadTwin(file)));
          }}
        />
      </label>
      <p>
        4 MiB maximum. Viewing requires an embedded, static core GLB 2.0. STEP
        and drawings remain source attachments; no automatic CAD conversion.
      </p>
      {preview && (
        <div aria-label="Import preview">
          <h3>Review {preview.filename}</h3>
          <p>
            {(preview.size / 1024).toFixed(1)} KiB · {preview.details.format}
          </p>
          {preview.details.notice && <p>{preview.details.notice}</p>}
          {preview.details.geometry_status && (
            <p>{preview.details.geometry_status}</p>
          )}
          {preview.details.aas_id && (
            <>
              <p>Equipment: {preview.details.name}</p>
              <details>
                <summary>Import provenance and compatibility</summary>
                <p>{preview.details.specification}</p>
                <p>{preview.details.aas_id}</p>
                <p>{preview.details.external_id}</p>
                <p>
                  Original package and unknown content are preserved. Full AAS
                  conformance is not claimed.
                </p>
              </details>
              {preview.details.properties?.map((p, i) => (
                <p key={i}>
                  {p.id}: {p.value}
                </p>
              ))}
              <ul>
                {preview.details.references?.map((r, i) => (
                  <li key={i}>
                    {r.id}: {r.status.replaceAll("_", " ")}{" "}
                    <code>{r.path}</code>
                  </li>
                ))}
              </ul>
              {Boolean(preview.details.unsupported?.length) && (
                <details>
                  <summary>Preserved unsupported content</summary>
                  <ul>
                    {preview.details.unsupported?.map((u, i) => (
                      <li key={i}>
                        {u.id} ({u.type})
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  const data = new FormData(event.currentTarget);
                  run(async () => {
                    const result = await twin<TwinAsset>(
                      `/imports/${preview.id}/commit`,
                      "POST",
                      {
                        name: data.get("name"),
                        serial: data.get("serial"),
                        geometry_file_id: data.get("geometry") || null,
                        include_documents: data.get("documents") === "on",
                      },
                      AbortSignal.timeout(90000),
                    );
                    await onSaved(result.id);
                    setPreview(null);
                  });
                }}
              >
                <label>
                  Equipment name
                  <input
                    name="name"
                    defaultValue={preview.details.name}
                    required
                    maxLength={120}
                  />
                </label>
                <label>
                  Installed serial number
                  <input name="serial" required maxLength={120} />
                </label>
                <label>
                  Embedded geometry to review
                  <select name="geometry">
                    <option value="">No geometry — attach a GLB later</option>
                    {preview.details.attachments
                      ?.filter((a) => a.details.format === "glb")
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.path}
                        </option>
                      ))}
                  </select>
                </label>
                {preview.details.attachments?.some((a) =>
                  /\.(txt|pdf)$/i.test(a.path),
                ) && (
                  <label>
                    <input type="checkbox" name="documents" />
                    Index embedded manuals in my Knowledge and link them to this
                    equipment. Existing Knowledge extraction and storage limits
                    apply.
                  </label>
                )}
                <ul aria-label="Preserved embedded files">
                  {preview.details.attachments?.map((a) => (
                    <li key={a.id}>
                      {a.path} · {a.details.format}{" "}
                      <a href={`/api/v1/twins/files/${a.id}/content`}>
                        Download preserved file
                      </a>
                    </li>
                  ))}
                </ul>
                <p>
                  Imported components are proposed from the geometry. Confirm
                  their identity, mappings and scale before activation.
                  Duplicate serials are rejected; repeat commit returns the
                  original installation.
                </p>
                <button>Commit reviewed equipment import</button>
              </form>
            </>
          )}
          {draftModel && (
            <>
              <p>
                Preview only. Confirm source units and map every visible part to
                a stable equipment component.
              </p>
              <div style={{ height: 320 }}>
                <Viewer
                  key={preview.id}
                  model={draftModel}
                  components={asset?.definition.components || []}
                  selected=""
                  onSelect={() => {}}
                  hidden={[]}
                  isolated={null}
                  transparent={false}
                  focus={0}
                  camera={null}
                  onCamera={() => {}}
                />
              </div>
              {asset && template ? (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    run(async () => {
                      const model = await twin<{ id: string }>(
                        "/models",
                        "POST",
                        {
                          file_id: preview.id,
                          template_id: template.id,
                          mappings: Object.entries(mapping).map(
                            ([node, component_id]) => ({ node, component_id }),
                          ),
                          unit,
                          meters_per_unit:
                            draftModel.definition.meters_per_unit,
                          provenance:
                            "User reviewed uploaded source, right-handed Y-up units and explicit component mapping",
                        },
                      );
                      await twin(`/assets/${asset.id}`, "PATCH", {
                        expected_revision: asset.revision,
                        stage: "preview",
                        model_id: model.id,
                      });
                      setPreview(null);
                      await onSaved(asset.id);
                    });
                  }}
                >
                  {preview.details.nodes?.map((node) => (
                    <label key={node.ref}>
                      Map {node.name}
                      <select
                        required
                        value={mapping[node.ref] || ""}
                        onChange={(e) =>
                          setMapping((current) => ({
                            ...current,
                            [node.ref]: e.target.value,
                          }))
                        }
                      >
                        <option value="">Choose stable component</option>
                        {template.definition.components
                          .filter((c) => c.renderable !== false)
                          .map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                      </select>
                    </label>
                  ))}
                  <label>
                    Prepared model units
                    <select
                      value={unit}
                      onChange={(e) => setUnit(e.target.value)}
                    >
                      <option value="m">Meters</option>
                      <option value="cm">Centimeters</option>
                      <option value="mm">Millimeters</option>
                    </select>
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={reviewScale}
                      onChange={(e) => setReviewScale(e.target.checked)}
                    />
                    I reviewed the component mapping, source units and scale.
                    This geometry is for visualization.
                  </label>
                  <button
                    disabled={
                      !reviewScale ||
                      Object.keys(mapping).length !==
                        preview.details.nodes?.length
                    }
                  >
                    Save reviewed model revision
                  </button>
                </form>
              ) : (
                <p>
                  Create or select an equipment instance before mapping the
                  model.
                </p>
              )}
            </>
          )}
          {asset && preview.filename.match(/\.(txt|pdf)$/i) && (
            <button
              onClick={() =>
                run(async () => {
                  await twin(
                    `/assets/${asset.id}/files/${preview.id}/index-document`,
                    "POST",
                  );
                  await onSaved(asset.id);
                })
              }
            >
              Link and index this maintenance document
            </button>
          )}
          <a href={`/api/v1/twins/files/${preview.id}/content`}>
            Download preserved original
          </a>
        </div>
      )}
      {asset?.definition.review_model_id && !asset.active_model_id && (
        <section>
          <h3>Imported model review</h3>
          <p>
            Confirm each proposed scene part, stable component and source scale
            before activating this imported revision.
          </p>
          {models
            .filter((m) => m.id === asset.definition.review_model_id)
            .map((m) => (
              <div key={m.id}>
                <p>
                  Units: {m.definition.unit}; {m.definition.frame}
                </p>
                <ul>
                  {m.definition.mappings.map((binding) => (
                    <li key={binding.node}>
                      {
                        m.definition.nodes.find((n) => n.ref === binding.node)
                          ?.name
                      }
                      :{" "}
                      {
                        template?.definition.components.find(
                          (c) => c.id === binding.component_id,
                        )?.name
                      }
                    </li>
                  ))}
                </ul>
                <p>{m.definition.provenance}</p>
                <label>
                  <input
                    type="checkbox"
                    checked={reviewScale}
                    onChange={(e) => setReviewScale(e.target.checked)}
                  />
                  I reviewed the imported mapping and model scale.
                </label>
                <button
                  disabled={!reviewScale}
                  onClick={() =>
                    run(async () => {
                      await twin(`/assets/${asset.id}`, "PATCH", {
                        expected_revision: asset.revision,
                        stage: "preview",
                        model_id: m.id,
                      });
                      await onSaved(asset.id);
                    })
                  }
                >
                  Review imported model mapping and scale
                </button>
              </div>
            ))}
        </section>
      )}
      {asset && (
        <>
          <p>Saved setup stage: {asset.definition.stage}</p>
          <div className="twin-stage-actions">
            {[
              "identity",
              "model",
              "mapping",
              "documents",
              "signals",
              "preview",
            ].map((stage) => (
              <button
                key={stage}
                aria-pressed={asset.definition.stage === stage}
                onClick={() =>
                  run(async () => {
                    await twin(`/assets/${asset.id}`, "PATCH", {
                      expected_revision: asset.revision,
                      stage,
                    });
                    await onSaved(asset.id);
                  })
                }
              >
                {stage[0].toUpperCase() + stage.slice(1)}
              </button>
            ))}
          </div>
          <button
            disabled={!asset.active_model_id}
            onClick={() =>
              run(async () => {
                await twin(`/assets/${asset.id}`, "PATCH", {
                  expected_revision: asset.revision,
                  stage: "active",
                });
                await onSaved(asset.id);
              })
            }
          >
            Activate reviewed workspace
          </button>
        </>
      )}
    </section>
  );
}
