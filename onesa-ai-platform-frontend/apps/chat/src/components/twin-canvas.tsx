"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  Component,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import * as THREE from "three";
import {
  GLTFLoader,
  type GLTF,
} from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import InspectionLayer from "./twin-inspection-layer";
import {
  capturePose,
  descendants,
  sectionPlane,
  type BaselinePose,
} from "../lib/twin-inspection";
import {
  BUDGET,
  inspectGlb,
  validateManifest,
  validateState,
  validateCommand,
  validateEvent,
  type ModelManifest,
  type ViewerState,
  type ViewerCommand,
  type ViewerEvent,
} from "../lib/twin-viewer-contract";

export type ModelLoader = (
  signal: AbortSignal,
  progress: (receivedBytes: number) => void,
) => Promise<ArrayBuffer>;
export type CommandRequest = { sequence: number; value: ViewerCommand };
export type EquipmentViewerProps = {
  manifest: ModelManifest;
  state: ViewerState;
  loadModel: ModelLoader;
  command?: CommandRequest | null;
  onEvent: (event: ViewerEvent) => void;
  fallback?: React.ReactNode;
};
export type Loaded = {
  gltf: GLTF;
  mapping: Map<THREE.Object3D, string>;
  loadMs: number;
  startedAt: number;
  triangles: number;
  manifest: ModelManifest;
  baselines: Map<THREE.Mesh, BaselinePose>;
  assembledBounds: THREE.Box3;
  dispose: () => void;
};

export function disposeModel(gltf: GLTF): void {
  const geometries = new Set<THREE.BufferGeometry>(),
    materials = new Set<THREE.Material>(),
    textures = new Set<THREE.Texture>();
  gltf.scene.traverse((object) => {
    if (object instanceof THREE.Mesh) {
      geometries.add(object.geometry);
      for (const material of Array.isArray(object.material)
        ? object.material
        : [object.material]) {
        materials.add(material);
        for (const value of Object.values(material))
          if (value instanceof THREE.Texture) textures.add(value);
      }
    }
  });
  geometries.forEach((value) => value.dispose());
  materials.forEach((value) => value.dispose());
  textures.forEach((value) => value.dispose());
  gltf.parser.associations.clear();
}

export async function prepareModel(
  manifest: ModelManifest,
  load: ModelLoader,
  signal: AbortSignal,
  progress: (received: number) => void,
): Promise<Loaded> {
  const started = performance.now(),
    buffer = await load(signal, progress);
  if (signal.aborted) throw new Error("Model load cancelled");
  if (buffer.byteLength !== manifest.artifact.byteLength)
    throw new Error("Model byte identity mismatch");
  const checksum = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", buffer)),
  )
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
  if (checksum !== manifest.artifact.sha256)
    throw new Error("Model content identity mismatch");
  const inspected = inspectGlb(buffer);
  if (
    inspected.nodes.length !== manifest.mappings.length ||
    manifest.mappings.some((m) => !inspected.nodes.includes(m.sceneNode))
  )
    throw new Error("Model revision mapping is incomplete");
  const gltf = await new GLTFLoader().parseAsync(buffer, "");
  try {
    const mapping = new Map<THREE.Object3D, string>(),
      bindings = new Map(
        manifest.mappings.map((m) => [m.sceneNode, m.componentId]),
      );
    const originals = new Set<THREE.Material>();
    gltf.scene.traverse((object) => {
      const node = gltf.parser.associations.get(object)?.nodes,
        id = node === undefined ? undefined : bindings.get(`node:${node}`);
      if (id) {
        mapping.set(object, id);
        object.traverse((child) => mapping.set(child, id));
      }
      if (object instanceof THREE.Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
        const values = Array.isArray(object.material)
          ? object.material
          : [object.material];
        values.forEach((m) => originals.add(m));
        object.material = Array.isArray(object.material)
          ? values.map((m) => m.clone())
          : values[0].clone();
      }
    });
    originals.forEach((value) => value.dispose());
    gltf.scene.applyMatrix4(new THREE.Matrix4().fromArray(manifest.transform));
    gltf.scene.scale.multiplyScalar(manifest.metersPerUnit);
    gltf.scene.updateMatrixWorld(true);
    let disposed = false;
    const result = {
      gltf,
      mapping,
      loadMs: performance.now() - started,
      startedAt: started,
      triangles: inspected.triangles,
      manifest,
      baselines: new Map(
        [...mapping.keys()]
          .filter(
            (object): object is THREE.Mesh => object instanceof THREE.Mesh,
          )
          .map((object) => [object, capturePose(object)]),
      ),
      assembledBounds: new THREE.Box3().setFromObject(gltf.scene),
      dispose: () => {
        if (!disposed) {
          disposed = true;
          disposeModel(gltf);
        }
      },
    };
    if (signal.aborted) {
      throw new Error("Model load cancelled");
    }
    return result;
  } catch (error) {
    disposeModel(gltf);
    throw error;
  }
}

function applyScene(
  loaded: Loaded,
  state: ViewerState,
  command: ViewerCommand | null,
) {
  const highlighted =
    command?.action === "highlight_components"
      ? command.componentIds
      : state.highlightedComponentIds;
  const selectedIds = descendants(loaded.manifest, state.selectedComponentId);
  const hiddenIds = new Set(
    state.hiddenComponentIds.flatMap((id) => [
      ...descendants(loaded.manifest, id),
    ]),
  );
  const highlightIds = new Set(
    highlighted.flatMap((id) => [...descendants(loaded.manifest, id)]),
  );
  const isolatedIds = descendants(loaded.manifest, state.isolatedComponentId);
  const housingIds = new Set(
    loaded.manifest.inspection?.housing_components || [],
  );
  for (const [object, id] of loaded.mapping)
    if (object instanceof THREE.Mesh) {
      object.visible =
        !hiddenIds.has(id) &&
        (!state.isolatedComponentId || isolatedIds.has(id));
      const values = Array.isArray(object.material)
        ? object.material
        : [object.material];
      for (const material of values)
        if (material instanceof THREE.MeshStandardMaterial) {
          const selected =
            (state.selectedComponentId !== null && selectedIds.has(id)) ||
            highlightIds.has(id);
          material.emissive.set(selected ? "#686acb" : "#000000");
          material.emissiveIntensity = selected ? 0.16 : 0;
          material.transparent =
            (state.transparentSurroundings && !selectedIds.has(id)) ||
            (Boolean(state.inspection?.ghost_housings) && housingIds.has(id));
          material.opacity = material.transparent ? 0.22 : 1;
          material.depthWrite = !material.transparent;
          material.needsUpdate = true;
        }
    }
}

function fit(
  camera: THREE.Camera,
  controls: OrbitControls,
  loaded: Loaded,
  command: ViewerCommand | null,
) {
  if (command?.action === "restore_viewpoint") {
    camera.position.fromArray(command.position);
    controls.target.fromArray(command.target);
  } else {
    const box = new THREE.Box3();
    const focus =
      command?.action === "focus_component" ? command.componentIds : null;
    const focusIds = focus
      ? new Set(focus.flatMap((id) => [...descendants(loaded.manifest, id)]))
      : null;
    for (const [object, id] of loaded.mapping)
      if (
        object instanceof THREE.Mesh &&
        object.visible &&
        (!focusIds || focusIds.has(id))
      )
        box.union(new THREE.Box3().setFromObject(object));
    if (box.isEmpty()) box.setFromObject(loaded.gltf.scene);
    const center = box.getCenter(new THREE.Vector3()),
      size = Math.max(0.05, box.getSize(new THREE.Vector3()).length());
    camera.position
      .copy(center)
      .add(new THREE.Vector3(size * 0.7, size * 0.55, size * 0.9));
    controls.target.copy(center);
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.near = Math.max(0.001, size / 1000);
      camera.far = Math.max(100, size * 100);
      camera.updateProjectionMatrix();
    }
  }
  controls.update();
}

const STATUS_COLORS = {
  normal: "#23894e",
  rule_alarm: "#c66413",
  bad: "#c33145",
  stale: "#8c6b18",
  unknown: "#707b8c",
};

function recordRender(
  element: HTMLDivElement | null,
  renderer: THREE.WebGLRenderer,
  loaded: Loaded,
  cpuSubmitMs: number,
) {
  if (!element) return;
  element.dataset.cpuSubmitMs = cpuSubmitMs.toFixed(2);
  element.dataset.renderCount = String(
    Number(element.dataset.renderCount || "0") + 1,
  );
  element.dataset.gpuGeometries = String(renderer.info.memory.geometries);
  element.dataset.drawCalls = String(renderer.info.render.calls);
  const canvas = renderer.domElement;
  const settled =
    canvas.clientWidth > 0 &&
    Math.abs(canvas.width / renderer.getPixelRatio() - canvas.clientWidth) <= 1;
  if (settled && !element.dataset.firstSettledFrameMs)
    element.dataset.firstSettledFrameMs = String(
      Math.round(performance.now() - loaded.startedAt),
    );
  if (!element.dataset.firstFrameMs)
    element.dataset.firstFrameMs = String(
      Math.round(performance.now() - loaded.startedAt),
    );
  element.dataset.visibleComponents = JSON.stringify([
    ...new Set(
      [...loaded.mapping]
        .filter(([object]) => object.visible)
        .map(([, id]) => id),
    ),
  ]);
}
function markers(loaded: Loaded, state: ViewerState) {
  return [
    ...new Set([
      ...state.observations.map((o) => o.componentId),
      ...state.annotations.map((a) => a.componentId),
      ...(state.selectedComponentId ? [state.selectedComponentId] : []),
    ]),
  ].map((id) => {
    const box = new THREE.Box3();
    const ids = descendants(loaded.manifest, id);
    for (const [object, component] of loaded.mapping)
      if (ids.has(component) && object instanceof THREE.Mesh)
        box.union(new THREE.Box3().setFromObject(object));
    const center = box.getCenter(new THREE.Vector3());
    center.y = box.max.y + 0.055;
    const observed = state.observations.filter((o) => o.componentId === id);
    const rank = ["rule_alarm", "bad", "stale", "unknown", "normal"];
    const status = observed.length
      ? observed
          .map((o) => o.status)
          .sort((a, b) => rank.indexOf(a) - rank.indexOf(b))[0]
      : "unknown";
    return {
      id,
      position: center.toArray() as [number, number, number],
      status,
      color: STATUS_COLORS[status],
      annotation: state.annotations.some((a) => a.componentId === id),
    };
  });
}
function updateMarkerPositions(
  loaded: Loaded,
  state: ViewerState,
  objects: Map<string, THREE.Mesh>,
) {
  for (const point of markers(loaded, state)) {
    objects.get(point.id)?.position.fromArray(point.position);
    objects
      .get("annotation-" + point.id)
      ?.position.fromArray([
        point.position[0],
        point.position[1] + 0.07,
        point.position[2],
      ]);
  }
}

function Scene({
  loaded,
  state,
  command,
  emit,
  metrics,
}: {
  loaded: Loaded;
  state: ViewerState;
  command: CommandRequest | null;
  emit: (event: ViewerEvent) => void;
  metrics: React.RefObject<HTMLDivElement | null>;
}) {
  const { camera, gl, invalidate, size, setDpr } = useThree(),
    controls = useRef<OrbitControls | null>(null);
  const markerObjects = useRef(new Map<string, THREE.Mesh>());
  const appliedCameraCommand = useRef<{
    model: Loaded;
    sequence: number | null;
  } | null>(null);
  const assetId = state.assetInstanceId;
  useEffect(() => {
    setDpr(
      size.width < 600
        ? BUDGET.mobileDpr
        : Math.min(window.devicePixelRatio, BUDGET.desktopDpr),
    );
  }, [size.width, setDpr]);
  useEffect(() => {
    const orbit = new OrbitControls(camera, gl.domElement);
    controls.current = orbit;
    orbit.enableDamping = false;
    orbit.minDistance = 0.02;
    orbit.maxDistance = 10000;
    const change = () => {
      invalidate();
      emit({
        schemaVersion: "1.0.0",
        type: "camera_changed",
        assetInstanceId: assetId,
        position: camera.position.toArray(),
        target: orbit.target.toArray(),
      });
    };
    orbit.addEventListener("change", change);
    return () => {
      orbit.removeEventListener("change", change);
      orbit.dispose();
      controls.current = null;
    };
  }, [camera, gl, invalidate, emit, assetId]);
  useEffect(() => {
    applyScene(loaded, state, command?.value || null);
    invalidate();
  }, [loaded, state, command, invalidate]);
  useEffect(() => {
    const sequence = command?.sequence ?? null;
    if (
      appliedCameraCommand.current?.model === loaded &&
      appliedCameraCommand.current.sequence === sequence
    )
      return;
    appliedCameraCommand.current = { model: loaded, sequence };
    if (controls.current && command?.value.action !== "highlight_components") {
      fit(camera, controls.current, loaded, command?.value || null);
      invalidate();
    }
  }, [loaded, command, camera, invalidate]);
  useFrame(({ scene, camera }) => {
    const submitted = performance.now();
    gl.render(scene, camera);
    recordRender(metrics.current, gl, loaded, performance.now() - submitted);
  }, 1);
  useFrame(() => updateMarkerPositions(loaded, state, markerObjects.current));
  const settled = useCallback(() => {
    if (!controls.current || command?.value.action === "restore_viewpoint")
      return;
    const scope = state.inspection?.scope;
    fit(
      camera,
      controls.current,
      loaded,
      scope
        ? {
            schemaVersion: "1.0.0",
            action: "focus_component",
            componentIds: [scope],
          }
        : null,
    );
    invalidate();
  }, [loaded, camera, state.inspection?.scope, command, invalidate]);
  const points = useMemo(() => markers(loaded, state), [loaded, state]);
  const select = (id: string) => {
    if (state.capabilities.selection)
      emit({
        schemaVersion: "1.0.0",
        type: "component_selected",
        assetInstanceId: assetId,
        componentId: id,
      });
  };
  return (
    <>
      <InspectionLayer
        loaded={loaded}
        state={state}
        metrics={metrics}
        onSettled={settled}
        onSelect={select}
      />
      <ambientLight intensity={0.55} />
      <directionalLight
        position={[3, 5, 4]}
        intensity={3}
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-4}
        shadow-camera-right={4}
        shadow-camera-top={4}
        shadow-camera-bottom={-4}
        shadow-normalBias={0.015}
      />
      <directionalLight position={[-3, 2, -2]} intensity={1.3} />
      <primitive
        object={loaded.gltf.scene}
        onClick={(event: {
          object: THREE.Object3D;
          point: THREE.Vector3;
          stopPropagation: () => void;
        }) => {
          if (!event.object.visible) return;
          const view = state.inspection;
          if (
            view?.section_enabled &&
            sectionPlane(
              loaded.assembledBounds,
              view.section_axis,
              view.section_position,
              view.section_flip,
            ).distanceToPoint(event.point) < -1e-6
          )
            return;
          const pickedMaterials =
            event.object instanceof THREE.Mesh
              ? Array.isArray(event.object.material)
                ? event.object.material
                : [event.object.material]
              : [];
          if (
            pickedMaterials.some(
              (material) => material.transparent && material.opacity < 0.3,
            )
          )
            return;
          let object: THREE.Object3D | null = event.object;
          while (object) {
            const id = loaded.mapping.get(object);
            if (id) {
              event.stopPropagation();
              select(id);
              return;
            }
            object = object.parent;
          }
        }}
      />
      <gridHelper
        args={[4, 20, "#838ba4", "#969ca9"]}
        position={[0, 0.005, 0]}
      />
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.002, 0]}
        receiveShadow
      >
        <planeGeometry args={[10, 10]} />
        <shadowMaterial transparent opacity={0.15} />
      </mesh>
      {state.capabilities.statusMarkers &&
        points
          .filter(
            (p) =>
              !state.hiddenComponentIds.includes(p.id) &&
              (!state.isolatedComponentId ||
                state.isolatedComponentId === p.id),
          )
          .map((point) => (
            <mesh
              key={point.id}
              ref={(mesh) => {
                if (mesh) markerObjects.current.set(point.id, mesh);
                else markerObjects.current.delete(point.id);
              }}
              position={point.position}
              onClick={() => select(point.id)}
            >
              <sphereGeometry args={[0.025, 10, 8]} />
              <meshBasicMaterial color={point.color} />
            </mesh>
          ))}
      {state.capabilities.annotations &&
        points
          .filter((p) => p.annotation)
          .map((point) => (
            <mesh
              key={`annotation-${point.id}`}
              ref={(mesh) => {
                if (mesh)
                  markerObjects.current.set("annotation-" + point.id, mesh);
                else markerObjects.current.delete("annotation-" + point.id);
              }}
              position={[
                point.position[0],
                point.position[1] + 0.07,
                point.position[2],
              ]}
              onClick={() =>
                emit({
                  schemaVersion: "1.0.0",
                  type: "annotation_requested",
                  assetInstanceId: assetId,
                  componentId: point.id,
                })
              }
            >
              <octahedronGeometry args={[0.025]} />
              <meshBasicMaterial color="#8265c9" />
            </mesh>
          ))}
    </>
  );
}

class Boundary extends Component<
  { children: React.ReactNode; fallback: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function ValidViewer({
  manifest,
  state,
  command,
  loadModel,
  onEvent,
  fallback: suppliedFallback,
}: EquipmentViewerProps) {
  const [loaded, setLoaded] = useState<Loaded | null>(null),
    [error, setError] = useState(""),
    [progress, setProgress] = useState(0);
  const metrics = useRef<HTMLDivElement>(null),
    cleanup = useRef<(() => void) | null>(null);
  const assetId = state.assetInstanceId;
  const emit = useCallback(
    (event: ViewerEvent) =>
      onEvent(validateEvent(event, { assetInstanceId: assetId }, manifest)),
    [onEvent, assetId, manifest],
  );
  useEffect(() => {
    const controller = new AbortController();
    let resource: Loaded | null = null;
    let active = true;
    prepareModel(manifest, loadModel, controller.signal, (received) => {
      if (active) setProgress(received);
    })
      .then((value) => {
        resource = value;
        if (active) setLoaded(value);
        else value.dispose();
      })
      .catch(() => {
        if (active && !controller.signal.aborted)
          setError(
            "The model is unavailable, invalid or exceeds the supported resource budget.",
          );
      });
    return () => {
      active = false;
      controller.abort();
      cleanup.current?.();
      cleanup.current = null;
      resource?.dispose();
    };
  }, [manifest, loadModel]);
  const fallback = suppliedFallback || (
    <p role="status">
      3D graphics are unavailable. Continue with the application’s equipment
      list and details.
    </p>
  );
  if (error)
    return (
      <div role="alert">
        <p>{error}</p>
        {fallback}
      </div>
    );
  if (!loaded)
    return (
      <p role="status">
        Loading reviewed model… {Math.ceil(progress / 1024)} KiB
      </p>
    );
  return (
    <Boundary fallback={fallback}>
      <div
        ref={metrics}
        data-testid="equipment-model-loaded"
        data-load-ms={Math.round(loaded.loadMs)}
        data-triangles={loaded.triangles}
        style={{ height: "100%", minHeight: 300, position: "relative" }}
      >
        <Canvas
          frameloop="demand"
          gl={{ stencil: true, antialias: true }}
          shadows
          dpr={[BUDGET.mobileDpr, BUDGET.desktopDpr]}
          camera={{ fov: 42, position: [3, 2, 4] }}
          fallback={fallback}
          onCreated={({ gl }) => {
            const lost = (event: Event) => {
              event.preventDefault();
              setError(
                "Graphics context lost. Equipment information remains available.",
              );
            };
            gl.domElement.addEventListener("webglcontextlost", lost);
            gl.domElement.setAttribute(
              "aria-label",
              "Equipment assembly. Use the application’s component list for keyboard selection.",
            );
            gl.domElement.setAttribute("role", "img");
            cleanup.current = () =>
              gl.domElement.removeEventListener("webglcontextlost", lost);
          }}
        >
          <Scene
            loaded={loaded}
            state={state}
            command={command || null}
            emit={emit}
            metrics={metrics}
          />
        </Canvas>
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            overflow: "hidden",
          }}
        >
          {manifest.components
            .filter(
              (c) =>
                c.id === state.selectedComponentId ||
                (state.inspection?.explode &&
                  c.renderable === false &&
                  c.parentId === (state.inspection.scope || null)),
            )
            .slice(0, 12)
            .map((c) => (
              <span
                key={c.id}
                data-world-label={c.id}
                style={{
                  position: "absolute",
                  display: "none",
                  padding: "3px 7px",
                  borderRadius: 4,
                  fontSize: 12,
                  whiteSpace: "nowrap",
                  transform: "translate(-50%,-110%)",
                  color:
                    state.appearance.theme === "dark" ? "#f0f3ff" : "#152943",
                  background:
                    state.appearance.theme === "dark"
                      ? "rgba(15,22,39,.9)"
                      : "rgba(255,255,255,.92)",
                }}
              >
                {c.label}
              </span>
            ))}
        </div>
      </div>
    </Boundary>
  );
}

export function EquipmentViewer(props: EquipmentViewerProps) {
  const manifestJSON = JSON.stringify(props.manifest),
    stateJSON = JSON.stringify(props.state),
    commandJSON = JSON.stringify(props.command || null);
  const manifest = useMemo(() => {
    try {
      return validateManifest(JSON.parse(manifestJSON));
    } catch {
      return null;
    }
  }, [manifestJSON]);
  const state = useMemo(() => {
    try {
      return manifest ? validateState(JSON.parse(stateJSON), manifest) : null;
    } catch {
      return null;
    }
  }, [stateJSON, manifest]);
  const command = useMemo(() => {
    try {
      const request = JSON.parse(commandJSON);
      return manifest && request
        ? {
            sequence: request.sequence,
            value: validateCommand(request.value, manifest),
          }
        : null;
    } catch {
      return undefined;
    }
  }, [commandJSON, manifest]);
  const validated =
    manifest && state && command !== undefined
      ? { manifest, state, command }
      : null;
  if (!validated)
    return (
      <div role="alert">
        Equipment viewer contract or model mapping is invalid. Use the
        application’s equipment details.
      </div>
    );
  return (
    <ValidViewer
      key={`${validated.manifest.modelRevision}:${validated.manifest.artifact.sha256}`}
      {...props}
      {...validated}
    />
  );
}
