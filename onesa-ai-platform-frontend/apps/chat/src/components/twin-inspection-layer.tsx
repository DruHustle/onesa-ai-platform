"use client";
import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as T from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import {
  DEFAULT_INSPECTION,
  type ViewerState,
  type InspectionControls,
} from "../lib/twin-viewer-contract";
import {
  descendants,
  inspectionPose,
  sectionPlane,
  solidContainsPoint,
} from "../lib/twin-inspection";
import type { Loaded } from "./twin-canvas";

type Resources = {
  plane: T.Plane;
  back: T.MeshBasicMaterial;
  front: T.MeshBasicMaterial;
  planeGeometry: T.PlaneGeometry;
  capMaterials: Map<string, T.MeshStandardMaterial>;
  guides: Map<string, T.Line>;
};
function createResources(loaded: Loaded): Resources {
  const plane = new T.Plane(new T.Vector3(1, 0, 0), 0);
  const base = {
    depthWrite: false,
    depthTest: false,
    colorWrite: false,
    clippingPlanes: [plane],
    stencilWrite: true,
    stencilFunc: T.AlwaysStencilFunc,
  };
  const back = new T.MeshBasicMaterial({
    ...base,
    side: T.BackSide,
    stencilFail: T.IncrementWrapStencilOp,
    stencilZFail: T.IncrementWrapStencilOp,
    stencilZPass: T.IncrementWrapStencilOp,
  });
  const front = new T.MeshBasicMaterial({
    ...base,
    side: T.FrontSide,
    stencilFail: T.DecrementWrapStencilOp,
    stencilZFail: T.DecrementWrapStencilOp,
    stencilZPass: T.DecrementWrapStencilOp,
  });
  const capMaterials = new Map<string, T.MeshStandardMaterial>(),
    guides = new Map<string, T.Line>();
  for (const [object, id] of loaded.mapping)
    if (object instanceof T.Mesh) {
      if (!capMaterials.has(id))
        capMaterials.set(
          id,
          new T.MeshStandardMaterial({
            color: "#d1ac70",
            metalness: 0.55,
            roughness: 0.4,
            side: T.DoubleSide,
            stencilWrite: true,
            stencilRef: 0,
            stencilFunc: T.NotEqualStencilFunc,
            stencilFail: T.ReplaceStencilOp,
            stencilZFail: T.ReplaceStencilOp,
            stencilZPass: T.ReplaceStencilOp,
          }),
        );
      if (!guides.has(id)) {
        const geometry = new T.BufferGeometry().setAttribute(
          "position",
          new T.Float32BufferAttribute(new Float32Array(6), 3),
        );
        const line = new T.Line(
          geometry,
          new T.LineBasicMaterial({
            color: "#8797b5",
            transparent: true,
            opacity: 0.7,
          }),
        );
        line.frustumCulled = false;
        line.renderOrder = 1100;
        guides.set(id, line);
      }
    }
  return {
    plane,
    back,
    front,
    planeGeometry: new T.PlaneGeometry(1, 1),
    capMaterials,
    guides,
  };
}
function disposeResources(resources: Resources) {
  resources.back.dispose();
  resources.front.dispose();
  resources.planeGeometry.dispose();
  resources.capMaterials.forEach((m) => m.dispose());
  resources.guides.forEach((line) => {
    line.geometry.dispose();
    (line.material as T.Material).dispose();
  });
}
function installEnvironment(scene: T.Scene, renderer: T.WebGLRenderer) {
  const room = new RoomEnvironment(),
    generator = new T.PMREMGenerator(renderer);
  const environment = generator.fromScene(room, 0.04);
  const previous = scene.environment;
  scene.environment = environment.texture;
  room.dispose();
  generator.dispose();
  return () => {
    if (scene.environment === environment.texture) scene.environment = previous;
    environment.dispose();
  };
}
function boxFor(loaded: Loaded, id: string): T.Box3 {
  const ids = descendants(loaded.manifest, id),
    box = new T.Box3();
  for (const [object, component] of loaded.mapping)
    if (ids.has(component) && object instanceof T.Mesh && object.visible)
      box.union(new T.Box3().setFromObject(object));
  return box;
}
function updateLabels(
  loaded: Loaded,
  element: HTMLDivElement | null,
  camera: T.Camera,
  size: { width: number; height: number },
  visible: boolean,
) {
  if (!element) return;
  for (const label of element.querySelectorAll<HTMLElement>(
    "[data-world-label]",
  )) {
    const box = boxFor(loaded, label.dataset.worldLabel || "");
    const point = box.getCenter(new T.Vector3());
    point.y = box.max.y + 0.035;
    point.project(camera);
    const shown =
      visible &&
      !box.isEmpty() &&
      point.z >= -1 &&
      point.z <= 1 &&
      Math.abs(point.x) <= 1.2 &&
      Math.abs(point.y) <= 1.2;
    label.style.display = shown ? "block" : "none";
    label.style.left = String(((point.x + 1) * size.width) / 2) + "px";
    label.style.top = String(((1 - point.y) * size.height) / 2) + "px";
  }
}
function updateGeometry(
  loaded: Loaded,
  view: InspectionControls,
  fraction: number,
  resources: Resources,
  stencilGroups: Map<T.Mesh, T.Group>,
  capPlanes: Map<T.Mesh, T.Mesh>,
  renderer: T.WebGLRenderer,
  metrics: HTMLDivElement | null,
  delta: number,
  snap: boolean,
) {
  const inspection = loaded.manifest.inspection,
    scopeIds = descendants(loaded.manifest, view.scope);
  const scopeMotion =
    inspection?.motions.find((m) => m.component_id === view.scope) || null;
  let restorationError = 0,
    settled = true;
  for (const [object, baseline] of loaded.baselines) {
    const id = loaded.mapping.get(object),
      motion = inspection?.motions.find((m) => m.component_id === id);
    const pose =
      motion && id && scopeIds.has(id)
        ? inspectionPose(baseline, motion, scopeMotion, view.explode)
        : baseline;
    const close =
      object.position.distanceToSquared(pose.position) < 1e-10 &&
      object.quaternion.angleTo(pose.quaternion) < 1e-5;
    if (snap || close) {
      object.position.copy(pose.position);
      object.quaternion.copy(pose.quaternion);
    } else {
      const weight = 1 - Math.exp(-12 * Math.min(0.1, delta));
      object.position.lerp(pose.position, weight);
      object.quaternion.slerp(pose.quaternion, weight);
      settled = false;
    }
    object.scale.copy(pose.scale);
    if (view.explode === 0)
      restorationError = Math.max(
        restorationError,
        object.position.distanceTo(baseline.position),
        1 - Math.abs(object.quaternion.dot(baseline.quaternion)),
      );
  }
  loaded.gltf.scene.updateMatrixWorld(true);
  resources.plane.copy(
    sectionPlane(
      loaded.assembledBounds,
      view.section_axis,
      view.section_position,
      view.section_flip,
    ),
  );
  renderer.localClippingEnabled = true;
  const solidIds = new Set(inspection?.closed_solids || []);
  let activeCaps = 0;
  for (const [object, id] of loaded.mapping)
    if (object instanceof T.Mesh) {
      object.renderOrder = 1000;
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];
      for (const material of materials) {
        const planes = view.section_enabled ? [resources.plane] : null;
        if (Boolean(material.clippingPlanes) !== Boolean(planes)) {
          material.clippingPlanes = planes;
          material.needsUpdate = true;
        } else if (planes && material.clippingPlanes)
          material.clippingPlanes[0] = resources.plane;
        material.clipShadows = true;
      }
      const stencil = stencilGroups.get(object),
        cap = capPlanes.get(object);
      const bounds = new T.Box3().setFromObject(object);
      const capVisible = Boolean(
        view.section_enabled &&
        view.section_caps &&
        object.visible &&
        solidIds.has(id) &&
        bounds.intersectsPlane(resources.plane) &&
        !materials.some((m) => m.transparent),
      );
      if (stencil) {
        stencil.visible = capVisible;
        stencil.matrix.copy(object.matrixWorld);
        stencil.matrixWorldNeedsUpdate = true;
      }
      if (cap) {
        cap.visible = capVisible;
        // Limit stencil fill to this mesh's projected bounding patch. A full-
        // viewport plane per small fastener creates unnecessary GPU overdraw.
        resources.plane.projectPoint(
          bounds.getCenter(new T.Vector3()),
          cap.position,
        );
        const extent = bounds.getSize(new T.Vector3()).length() * 1.01;
        cap.scale.set(extent, extent, 1);
        cap.quaternion.setFromUnitVectors(
          new T.Vector3(0, 0, 1),
          resources.plane.normal,
        );
        if (capVisible) activeCaps++;
        const source = materials[0],
          target = resources.capMaterials.get(id);
        if (source instanceof T.MeshStandardMaterial && target) {
          target.emissive.copy(source.emissive);
          target.emissiveIntensity = source.emissiveIntensity;
          target.opacity = 1;
          target.depthWrite = true;
        }
      }
      const line = resources.guides.get(id),
        baseline = loaded.baselines.get(object);
      if (line && baseline) {
        line.visible = Boolean(
          view.guides && fraction > 0.001 && object.visible && scopeIds.has(id),
        );
        const origin = baseline.position.clone();
        object.parent?.localToWorld(origin);
        const current = object.getWorldPosition(new T.Vector3()),
          p = line.geometry.getAttribute("position");
        p.setXYZ(0, origin.x, origin.y, origin.z);
        p.setXYZ(1, current.x, current.y, current.z);
        p.needsUpdate = true;
      }
    }
  if (metrics) {
    metrics.dataset.explodeFraction = fraction.toFixed(4);
    metrics.dataset.assembledRestorationError = String(
      Math.abs(restorationError),
    );
    metrics.dataset.sectionActive = String(view.section_enabled);
    metrics.dataset.sectionCaps = String(activeCaps);
    metrics.dataset.inspectionSettled = String(settled);
  }
  return settled;
}
export default function InspectionLayer({
  loaded,
  state,
  metrics,
  onSettled,
  onSelect,
}: {
  loaded: Loaded;
  state: ViewerState;
  metrics: React.RefObject<HTMLDivElement | null>;
  onSettled: () => void;
  onSelect: (id: string) => void;
}) {
  const { gl, scene, camera, size, invalidate } = useThree();
  const resources = useMemo(() => createResources(loaded), [loaded]);
  const stencilGroups = useRef(new Map<T.Mesh, T.Group>()),
    capPlanes = useRef(new Map<T.Mesh, T.Mesh>());
  const progress = useRef({ value: 0, target: 0, settled: true }),
    reduced = useRef(false);
  const view = state.inspection || DEFAULT_INSPECTION;
  useEffect(() => installEnvironment(scene, gl), [scene, gl]);
  useEffect(() => () => disposeResources(resources), [resources]);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => {
      reduced.current = query.matches;
      invalidate();
    };
    change();
    query.addEventListener("change", change);
    return () => query.removeEventListener("change", change);
  }, [invalidate]);
  useEffect(() => {
    progress.current.target = loaded.manifest.inspection ? view.explode : 0;
    progress.current.settled = false;
    invalidate();
  }, [view.explode, view.scope, loaded, invalidate]);
  useEffect(() => {
    invalidate();
  }, [view, invalidate]);
  useFrame((_frame, delta) => {
    const motion = progress.current;
    motion.value = reduced.current
      ? motion.target
      : T.MathUtils.damp(motion.value, motion.target, 12, Math.min(0.1, delta));
    if (Math.abs(motion.value - motion.target) < 0.0005)
      motion.value = motion.target;
    const posesSettled = updateGeometry(
      loaded,
      view,
      motion.value,
      resources,
      stencilGroups.current,
      capPlanes.current,
      gl,
      metrics.current,
      delta,
      reduced.current,
    );
    updateLabels(loaded, metrics.current, camera, size, view.labels);
    if (motion.value !== motion.target || !posesSettled) invalidate();
    else if (!motion.settled) {
      motion.settled = true;
      onSettled();
    }
  });
  const solids = new Set(loaded.manifest.inspection?.closed_solids || []);
  const meshes = [...loaded.mapping].filter(
    (entry): entry is [T.Mesh, string] => entry[0] instanceof T.Mesh,
  );
  return (
    <>
      {meshes
        .filter(([, id]) => solids.has(id))
        .map(([object, id], i) => (
          <group key={object.uuid} dispose={null}>
            <group
              matrixAutoUpdate={false}
              ref={(group) => {
                if (group) stencilGroups.current.set(object, group);
                else stencilGroups.current.delete(object);
              }}
            >
              <mesh
                geometry={object.geometry}
                material={resources.back}
                renderOrder={i * 3 + 1}
                dispose={null}
              />
              <mesh
                geometry={object.geometry}
                material={resources.front}
                renderOrder={i * 3 + 1}
                dispose={null}
              />
            </group>
            <mesh
              ref={(mesh) => {
                if (mesh) capPlanes.current.set(object, mesh);
                else capPlanes.current.delete(object);
              }}
              geometry={resources.planeGeometry}
              material={resources.capMaterials.get(id)}
              renderOrder={i * 3 + 2}
              onClick={(event) => {
                if (object.visible && solidContainsPoint(object, event.point)) {
                  event.stopPropagation();
                  onSelect(id);
                }
              }}
              onAfterRender={(renderer) => renderer.clearStencil()}
              dispose={null}
            />
          </group>
        ))}
      {[...resources.guides].map(([id, line]) => (
        <primitive key={id} object={line} dispose={null} />
      ))}
    </>
  );
}
