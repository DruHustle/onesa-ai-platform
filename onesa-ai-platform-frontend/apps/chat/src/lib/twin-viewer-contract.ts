import { z } from "zod";

export const CONTRACT_VERSION = "1.0.0" as const;
export const BUDGET = {
  maxBytes: 4 * 1024 * 1024,
  maxNodes: 100,
  maxTriangles: 100000,
  maxVertices: 200000,
  mobileDpr: 1,
  desktopDpr: 1.5,
} as const;
const id = z
  .string()
  .min(1)
  .max(160)
  .regex(/^[A-Za-z0-9_.:-]+$/);
const finite = z.number().finite().min(-1e9).max(1e9);
const vector3 = z.tuple([finite, finite, finite]);
const instant = z.iso.datetime({ offset: true });
export const componentSchema = z.strictObject({
  id,
  label: z.string().min(1).max(120),
  parentId: id.nullable(),
  renderable: z.boolean().optional(),
  inventory: z.enum(["assembly", "part", "combined", "unavailable"]).optional(),
  note: z.string().max(1000).optional(),
  material: z.string().max(200).optional(),
  housing: z.boolean().optional(),
});
export const inspectionSchema = z.strictObject({
  version: z.literal("1.0.0"),
  reference: z.string().min(1).max(160),
  description: z.string().min(1).max(2000),
  motions: z
    .array(
      z.strictObject({
        component_id: id,
        translation: z.tuple([
          finite.min(-10).max(10),
          finite.min(-10).max(10),
          finite.min(-10).max(10),
        ]),
        rotation: z.tuple([
          finite.min(-3.142).max(3.142),
          finite.min(-3.142).max(3.142),
          finite.min(-3.142).max(3.142),
        ]),
        pivot: z.tuple([
          finite.min(-1000).max(1000),
          finite.min(-1000).max(1000),
          finite.min(-1000).max(1000),
        ]),
      }),
    )
    .min(1)
    .max(100),
  closed_solids: z.array(id).max(100),
  housing_components: z.array(id).max(100),
  cover_components: z.array(id).max(100).optional(),
  scope_notes: z.array(z.string().max(1000)).max(20),
  unavailable: z.array(z.string().max(1000)).max(100),
});
export const inspectionViewSchema = z.strictObject({
  explode: finite.min(0).max(1),
  scope: id.nullable(),
  section_enabled: z.boolean(),
  section_axis: z.enum(["x", "y", "z"]),
  section_position: finite.min(-1).max(1),
  section_flip: z.boolean(),
  section_caps: z.boolean(),
  guides: z.boolean(),
  labels: z.boolean(),
  ghost_housings: z.boolean(),
});
export type InspectionControls = z.infer<typeof inspectionViewSchema>;
export const DEFAULT_INSPECTION: InspectionControls = {
  explode: 0,
  scope: null,
  section_enabled: false,
  section_axis: "x",
  section_position: 0,
  section_flip: false,
  section_caps: true,
  guides: false,
  labels: true,
  ghost_housings: false,
};
export const manifestShape = z.strictObject({
  schemaVersion: z.literal(CONTRACT_VERSION),
  modelRevision: id,
  artifact: z.strictObject({
    sha256: z.string().regex(/^[a-f0-9]{64}$/),
    byteLength: z.number().int().positive().max(BUDGET.maxBytes),
    mediaType: z.literal("model/gltf-binary"),
  }),
  provenance: z.strictObject({
    description: z.string().min(1).max(2000),
    rights: z.string().min(1).max(2000),
    illustrative: z.boolean(),
  }),
  unit: z.enum(["m", "cm", "mm"]),
  metersPerUnit: z.number().positive().max(1),
  coordinateFrame: z.literal("right-handed-y-up"),
  transform: z.array(finite).length(16),
  components: z.array(componentSchema).min(1).max(100),
  mappings: z
    .array(
      z.strictObject({
        sceneNode: z.string().regex(/^node:[0-9]{1,3}$/),
        componentId: id,
      }),
    )
    .min(1)
    .max(100),
  inspection: inspectionSchema.nullable().optional(),
});
export const observationSchema = z.strictObject({
  componentId: id,
  metric: id,
  value: finite.nullable(),
  unit: z.string().min(1).max(24),
  observedAt: instant.nullable(),
  ingestedAt: instant.nullable(),
  sourceId: id,
  quality: z.enum(["good", "bad", "unknown", "uncertain"]),
  freshness: z.enum(["fresh", "stale", "unknown"]),
  connection: z.enum(["connected", "disconnected", "unknown"]),
  mode: z.enum(["live", "simulated", "replay"]),
  status: z.enum(["normal", "rule_alarm", "bad", "stale", "unknown"]),
});
export const annotationSchema = z.strictObject({
  id,
  componentId: id,
  text: z.string().min(1).max(2000),
});
export const stateShape = z.strictObject({
  schemaVersion: z.literal(CONTRACT_VERSION),
  assetInstanceId: id,
  selectedComponentId: id.nullable(),
  highlightedComponentIds: z.array(id).max(100),
  hiddenComponentIds: z.array(id).max(100),
  isolatedComponentId: id.nullable(),
  transparentSurroundings: z.boolean(),
  inspection: inspectionViewSchema.optional(),
  observations: z.array(observationSchema).max(640),
  annotations: z.array(annotationSchema).max(100),
  appearance: z.strictObject({
    theme: z.enum(["light", "dark"]),
    locale: z.string().min(2).max(20),
  }),
  capabilities: z.strictObject({
    selection: z.boolean(),
    annotations: z.boolean(),
    statusMarkers: z.boolean(),
  }),
});
export const commandShape = z.discriminatedUnion("action", [
  z.strictObject({
    schemaVersion: z.literal(CONTRACT_VERSION),
    action: z.enum(["focus_component", "highlight_components"]),
    componentIds: z.array(id).min(1).max(100),
  }),
  z.strictObject({
    schemaVersion: z.literal(CONTRACT_VERSION),
    action: z.enum(["fit", "reset"]),
  }),
  z.strictObject({
    schemaVersion: z.literal(CONTRACT_VERSION),
    action: z.literal("restore_viewpoint"),
    position: vector3,
    target: vector3,
  }),
]);
export const eventShape = z.discriminatedUnion("type", [
  z.strictObject({
    schemaVersion: z.literal(CONTRACT_VERSION),
    type: z.literal("component_selected"),
    assetInstanceId: id,
    componentId: id,
  }),
  z.strictObject({
    schemaVersion: z.literal(CONTRACT_VERSION),
    type: z.literal("camera_changed"),
    assetInstanceId: id,
    position: vector3,
    target: vector3,
  }),
  z.strictObject({
    schemaVersion: z.literal(CONTRACT_VERSION),
    type: z.literal("annotation_requested"),
    assetInstanceId: id,
    componentId: id,
  }),
]);
export type ModelManifest = z.infer<typeof manifestShape>;
export type ViewerState = z.infer<typeof stateShape>;
export type ViewerCommand = z.infer<typeof commandShape>;
export type ViewerEvent = z.infer<typeof eventShape>;

// Schema validation is interpreted (jitless) per call; importing this library does
// not change another application's Zod configuration or require unsafe-eval CSP.
export function validateManifest(input: unknown): ModelManifest {
  const result = manifestShape.parse(input, { jitless: true });
  const ids = new Set(result.components.map((c) => c.id));
  if (
    ids.size !== result.components.length ||
    new Set(result.mappings.map((m) => m.sceneNode)).size !==
      result.mappings.length ||
    result.mappings.some((m) => !ids.has(m.componentId)) ||
    new Set(result.mappings.map((m) => m.componentId)).size !==
      result.components.filter((c) => c.renderable !== false).length ||
    result.mappings.some(
      (m) =>
        result.components.find((c) => c.id === m.componentId)?.renderable ===
        false,
    )
  )
    throw new Error("Ambiguous or unresolved model component mapping");
  const parents = new Map(result.components.map((c) => [c.id, c.parentId]));
  for (const c of result.components) {
    const seen = new Set<string>();
    let current: string | null = c.id;
    while (current) {
      if (seen.has(current) || !ids.has(current))
        throw new Error("Cyclic or unresolved component hierarchy");
      seen.add(current);
      current = parents.get(current) || null;
    }
  }
  if (
    result.metersPerUnit !== { m: 1, cm: 0.01, mm: 0.001 }[result.unit] ||
    [3, 7, 11, 15].some(
      (index, i) => result.transform[index] !== [0, 0, 0, 1][i],
    )
  )
    throw new Error("Model unit or affine transform mismatch");
  if (result.inspection) {
    const metadata = result.inspection;
    if (
      metadata.motions.length !== ids.size ||
      new Set(metadata.motions.map((m) => m.component_id)).size !== ids.size ||
      metadata.motions.some((m) => !ids.has(m.component_id)) ||
      [
        ...metadata.closed_solids,
        ...metadata.housing_components,
        ...(metadata.cover_components || []),
      ].some(
        (value) =>
          !result.components.some(
            (c) => c.id === value && c.renderable !== false,
          ),
      )
    )
      throw new Error("Authored inspection metadata crosses the model mapping");
  }
  return result;
}
export function validateState(
  input: unknown,
  manifest: ModelManifest,
): ViewerState {
  const result = stateShape.parse(input, { jitless: true });
  const ids = new Set(manifest.components.map((c) => c.id));
  for (const value of [
    result.selectedComponentId,
    result.isolatedComponentId,
    result.inspection?.scope || null,
    ...result.hiddenComponentIds,
    ...result.highlightedComponentIds,
    ...result.observations.map((o) => o.componentId),
    ...result.annotations.map((a) => a.componentId),
  ])
    if (value !== null && !ids.has(value))
      throw new Error("Viewer state crosses model component boundary");
  for (const observation of result.observations)
    if (
      (observation.value === null ||
        observation.observedAt === null ||
        observation.quality !== "good" ||
        observation.freshness !== "fresh") &&
      observation.status === "normal"
    )
      throw new Error("Missing or invalid observations cannot appear healthy");
  return result;
}
export function validateCommand(
  input: unknown,
  manifest: ModelManifest,
): ViewerCommand {
  const result = commandShape.parse(input, { jitless: true });
  if (
    "componentIds" in result &&
    result.componentIds.some(
      (id) => !manifest.components.some((c) => c.id === id),
    )
  )
    throw new Error("Viewer command references an unknown component");
  return result;
}
export function validateEvent(
  input: unknown,
  state: Pick<ViewerState, "assetInstanceId">,
  manifest: ModelManifest,
): ViewerEvent {
  const result = eventShape.parse(input, { jitless: true });
  if (
    result.assetInstanceId !== state.assetInstanceId ||
    ("componentId" in result &&
      !manifest.components.some((c) => c.id === result.componentId))
  )
    throw new Error(
      "Viewer event crosses asset instance or component boundary",
    );
  return result;
}

export function inspectGlb(buffer: ArrayBuffer): {
  nodes: string[];
  triangles: number;
} {
  if (buffer.byteLength < 28 || buffer.byteLength > BUDGET.maxBytes)
    throw new Error("GLB byte budget exceeded");
  const view = new DataView(buffer);
  if (
    view.getUint32(0, true) !== 0x46546c67 ||
    view.getUint32(4, true) !== 2 ||
    view.getUint32(8, true) !== buffer.byteLength ||
    view.getUint32(16, true) !== 0x4e4f534a
  )
    throw new Error("A complete core GLB 2.0 is required");
  const length = view.getUint32(12, true);
  if (20 + length + 8 > buffer.byteLength || length % 4)
    throw new Error("Invalid GLB chunk");
  const model = JSON.parse(
    new TextDecoder().decode(new Uint8Array(buffer, 20, length)),
  );
  if (
    model.asset?.version !== "2.0" ||
    !Array.isArray(model.nodes) ||
    !model.nodes.length ||
    model.nodes.length > BUDGET.maxNodes ||
    model.buffers?.length !== 1 ||
    model.buffers[0].uri ||
    [
      "images",
      "textures",
      "skins",
      "animations",
      "extensionsUsed",
      "extensionsRequired",
    ].some((key) => model[key]?.length)
  )
    throw new Error("Unsupported GLB resources or complexity");
  const binStart = 20 + length;
  if (
    view.getUint32(binStart + 4, true) !== 0x004e4942 ||
    binStart + 8 + view.getUint32(binStart, true) !== buffer.byteLength
  )
    throw new Error("Invalid embedded model buffer");
  let triangles = 0;
  for (const mesh of model.meshes || [])
    for (const primitive of mesh.primitives || []) {
      const accessor =
        model.accessors?.[primitive.indices ?? primitive.attributes?.POSITION];
      if (
        !accessor ||
        (primitive.mode !== undefined && primitive.mode !== 4) ||
        !Number.isSafeInteger(accessor.count) ||
        accessor.count <= 0
      )
        throw new Error("Unsupported mesh primitive");
      triangles += Math.floor(accessor.count / 3);
    }
  if (!triangles || triangles > BUDGET.maxTriangles)
    throw new Error("GLB triangle budget exceeded");
  return {
    nodes: model.nodes.flatMap((n: { mesh?: number }, i: number) =>
      n.mesh === undefined ? [] : [`node:${i}`],
    ),
    triangles,
  };
}
