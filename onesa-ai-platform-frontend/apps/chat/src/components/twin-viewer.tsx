"use client";
// Onesa owns delivery, identity, validation and rendering; no peer app dependency.
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  EquipmentViewer,
  type CommandRequest,
  type ModelLoader,
} from "./twin-canvas";
import type {
  ModelManifest,
  ViewerState,
  ViewerEvent,
  InspectionControls,
} from "../lib/twin-viewer-contract";
import { DEFAULT_INSPECTION } from "../lib/twin-viewer-contract";
import type { Component, Model, Signal, Note } from "../lib/twins";

type Props = {
  model: Model;
  components: Component[];
  selected: string;
  onSelect: (id: string) => void;
  hidden: string[];
  isolated: string | null;
  transparent: boolean;
  focus: number;
  camera: number[] | null;
  onCamera: (camera: number[]) => void;
  assetId?: string;
  signals?: Signal[];
  annotations?: Note[];
  highlights?: string[];
  inspection?: InspectionControls;
};

export default function TwinViewer({
  model,
  components,
  selected,
  onSelect,
  hidden,
  isolated,
  transparent,
  focus,
  camera,
  onCamera,
  assetId = "model-preview",
  signals = [],
  annotations = [],
  highlights = [],
  inspection = DEFAULT_INSPECTION,
}: Props) {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const changed = () => setTheme(query.matches ? "dark" : "light");
    changed();
    query.addEventListener("change", changed);
    return () => query.removeEventListener("change", changed);
  }, []);
  const manifest = useMemo<ModelManifest>(
    () => ({
      schemaVersion: "1.0.0",
      modelRevision: model.id,
      artifact: {
        sha256: model.definition.sha256,
        byteLength: model.definition.byte_length,
        mediaType: "model/gltf-binary",
      },
      provenance: {
        description: model.definition.provenance,
        rights: "Owner-authorized uploaded model; retained provenance applies",
        illustrative: model.definition.provenance
          .toLowerCase()
          .includes("illustrative"),
      },
      unit: model.definition.unit as "m" | "cm" | "mm",
      metersPerUnit: model.definition.meters_per_unit,
      coordinateFrame: "right-handed-y-up",
      transform: model.definition.transform,
      components:
        assetId === "model-preview"
          ? model.definition.nodes.map((n) => ({
              id: "preview-" + n.ref,
              label: n.name,
              parentId: null,
            }))
          : components.map((c) => ({
              id: c.template_component_id,
              label: c.name,
              renderable: c.renderable,
              inventory: c.inventory,
              note: c.inventory_note,
              material: c.material,
              housing: c.housing,
              parentId:
                components.find((p) => p.id === c.parent_id)
                  ?.template_component_id || null,
            })),
      mappings:
        assetId === "model-preview"
          ? model.definition.nodes.map((n) => ({
              sceneNode: n.ref,
              componentId: "preview-" + n.ref,
            }))
          : model.definition.mappings.map((m) => ({
              sceneNode: m.node,
              componentId: m.component_id,
            })),
      inspection:
        assetId === "model-preview" ? null : model.definition.inspection,
    }),
    [model, components, assetId],
  );
  const templateId = useCallback(
    (id: string) =>
      components.find((c) => c.id === id)?.template_component_id || null,
    [components],
  );
  const normalized = useMemo<ViewerState>(
    () => ({
      schemaVersion: "1.0.0",
      assetInstanceId: assetId,
      selectedComponentId: templateId(selected),
      highlightedComponentIds: highlights
        .map(templateId)
        .filter((v): v is string => v !== null),
      hiddenComponentIds: hidden
        .map(templateId)
        .filter((v): v is string => v !== null),
      isolatedComponentId: isolated ? templateId(isolated) : null,
      transparentSurroundings: transparent,
      inspection: {
        ...inspection,
        scope: inspection.scope ? templateId(inspection.scope) : null,
      },
      observations: signals.map((s) => ({
        componentId: templateId(s.binding.component_id) || "invalid-component",
        metric: s.binding.metric,
        value: s.reading?.value ?? null,
        unit: s.reading?.unit || s.binding.unit,
        observedAt: s.reading?.observed_at || null,
        ingestedAt: s.reading?.ingested_at || null,
        sourceId: s.source_id,
        quality:
          (s.reading?.quality as "good" | "bad" | "unknown") || "unknown",
        freshness:
          s.freshness === "good" || s.freshness === "bad"
            ? "fresh"
            : s.freshness === "stale"
              ? "stale"
              : "unknown",
        connection:
          s.connection === "connected"
            ? "connected"
            : s.connection === "disconnected"
              ? "disconnected"
              : "unknown",
        mode: (s.reading?.mode || "simulated") as
          "live" | "simulated" | "replay",
        status:
          s.freshness === "stale"
            ? "stale"
            : s.freshness === "bad"
              ? "bad"
              : s.freshness === "good"
                ? s.rule_state === "alarm"
                  ? "rule_alarm"
                  : "normal"
                : "unknown",
      })),
      annotations: annotations
        .filter(
          (n) =>
            n.kind === "annotation" &&
            templateId(n.component_id) &&
            n.payload.text,
        )
        .map((n) => ({
          id: n.id,
          componentId: templateId(n.component_id)!,
          text: n.payload.text!,
        })),
      appearance: { theme, locale: "en" },
      capabilities: { selection: true, annotations: true, statusMarkers: true },
    }),
    [
      assetId,
      selected,
      hidden,
      isolated,
      transparent,
      signals,
      annotations,
      templateId,
      theme,
      highlights,
      inspection,
    ],
  );
  const command = useMemo<CommandRequest | null>(
    () =>
      camera?.length === 6
        ? {
            sequence: focus,
            value: {
              schemaVersion: "1.0.0",
              action: "restore_viewpoint",
              position: camera.slice(0, 3) as [number, number, number],
              target: camera.slice(3) as [number, number, number],
            },
          }
        : focus > 0 && templateId(selected)
          ? {
              sequence: focus,
              value: {
                schemaVersion: "1.0.0",
                action: "focus_component",
                componentIds: [templateId(selected)!],
              },
            }
          : focus < 0
            ? {
                sequence: focus,
                value: { schemaVersion: "1.0.0", action: "fit" },
              }
            : null,
    [camera, focus, selected, templateId],
  );
  const onEvent = useCallback(
    (event: ViewerEvent) => {
      if (event.type === "camera_changed")
        onCamera([...event.position, ...event.target]);
      else {
        const installed = components.find(
          (c) => c.template_component_id === event.componentId,
        );
        if (installed) onSelect(installed.id);
      }
    },
    [onCamera, onSelect, components],
  );
  const loadModel = useCallback<ModelLoader>(
    async (signal, progress) => {
      const response = await fetch(
        `/api/v1/twins/files/${encodeURIComponent(model.file_id)}/content`,
        {
          credentials: "same-origin",
          cache: "no-store",
          signal: AbortSignal.any([signal, AbortSignal.timeout(45000)]),
        },
      );
      if (response.status === 401)
        window.dispatchEvent(new Event("onesa-session-expired"));
      if (!response.ok)
        throw new Error("Onesa private model delivery unavailable");
      const reader = response.body?.getReader();
      if (!reader) throw new Error("Model stream unavailable");
      const chunks: Uint8Array[] = [];
      let size = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.length;
          if (size > 4 * 1024 * 1024)
            throw new Error("Model byte budget exceeded");
          chunks.push(value);
          progress(size);
        }
      } catch (error) {
        await reader.cancel();
        throw error;
      }
      const bytes = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.length;
      }
      return bytes.buffer;
    },
    [model.file_id],
  );
  return (
    <EquipmentViewer
      manifest={manifest}
      state={normalized}
      command={command}
      loadModel={loadModel}
      onEvent={onEvent}
      fallback={
        <p role="status">
          3D graphics are unavailable. Continue with the Onesa component list
          and Details, History and Documents panels.
        </p>
      }
    />
  );
}
