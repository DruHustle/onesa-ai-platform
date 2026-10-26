import * as THREE from "three";
import type { ModelManifest } from "./twin-viewer-contract";

// Measure active wall time from the requested transition, excluding idle time.
// A slow renderer must reach an exact pose on its next frame after this bound.
export function inspectionAnimationFrame(elapsedMs: number, frameSeconds: number) {
  const elapsed = Number.isFinite(elapsedMs) ? Math.max(0, elapsedMs) : 0;
  const frame = Number.isFinite(frameSeconds) ? Math.max(0, frameSeconds) : 0;
  return { seconds: Math.min(frame, elapsed / 1000, 0.6), snap: elapsed >= 600 };
}

export function descendants(
  manifest: ModelManifest,
  parent: string | null,
): Set<string> {
  if (!parent) return new Set(manifest.components.map((c) => c.id));
  const result = new Set([parent]);
  for (let pass = 0; pass < manifest.components.length; pass++) {
    const count = result.size;
    for (const c of manifest.components)
      if (c.parentId && result.has(c.parentId)) result.add(c.id);
    if (result.size === count) break;
  }
  return result;
}

export type BaselinePose = {
  position: THREE.Vector3;
  quaternion: THREE.Quaternion;
  scale: THREE.Vector3;
};
export function capturePose(object: THREE.Object3D): BaselinePose {
  return {
    position: object.position.clone(),
    quaternion: object.quaternion.clone(),
    scale: object.scale.clone(),
  };
}

// Every frame derives from the immutable assembled baseline. Logical ancestors
// never move: an authored absolute part displacement is applied exactly once.
export function inspectionPose(
  baseline: BaselinePose,
  motion: NonNullable<ModelManifest["inspection"]>["motions"][number],
  scopeMotion:
    NonNullable<ModelManifest["inspection"]>["motions"][number] | null,
  amount: number,
): BaselinePose {
  const fraction = Math.max(0, Math.min(1, amount));
  if (fraction === 0)
    return {
      position: baseline.position.clone(),
      quaternion: baseline.quaternion.clone(),
      scale: baseline.scale.clone(),
    };
  const delta = new THREE.Vector3().fromArray(motion.translation);
  if (scopeMotion)
    delta.sub(new THREE.Vector3().fromArray(scopeMotion.translation));
  delta.multiplyScalar(fraction);
  const rotation = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(
      motion.rotation[0] * fraction,
      motion.rotation[1] * fraction,
      motion.rotation[2] * fraction,
    ),
  );
  const pivot = new THREE.Vector3().fromArray(motion.pivot);
  return {
    position: baseline.position
      .clone()
      .sub(pivot)
      .applyQuaternion(rotation)
      .add(pivot)
      .add(delta),
    quaternion: rotation.multiply(baseline.quaternion),
    scale: baseline.scale.clone(),
  };
}

export function sectionPlane(
  bounds: THREE.Box3,
  axis: "x" | "y" | "z",
  position: number,
  flip: boolean,
): THREE.Plane {
  const direction = new THREE.Vector3(
    axis === "x" ? 1 : 0,
    axis === "y" ? 1 : 0,
    axis === "z" ? 1 : 0,
  );
  const point = bounds
    .getCenter(new THREE.Vector3())
    .addScaledVector(
      direction,
      (bounds.getSize(new THREE.Vector3())[axis] *
        Math.max(-1, Math.min(1, position))) /
        2,
    );
  return new THREE.Plane().setFromNormalAndCoplanarPoint(
    direction.multiplyScalar(flip ? -1 : 1),
    point,
  );
}

// Non-zero oriented winding, matching the stencil cap. An infinite cap plane
// must never make an empty bore/cavity clickable as if it contained material.
export function solidContainsPoint(
  mesh: THREE.Mesh,
  point: THREE.Vector3,
): boolean {
  const local = mesh.worldToLocal(point.clone());
  const material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  const probe = new THREE.Mesh(mesh.geometry, material);
  const ray = new THREE.Raycaster(
    local,
    new THREE.Vector3(0.913, 0.237, 0.331).normalize(),
    1e-7,
  );
  const hits = ray.intersectObject(probe, false);
  material.dispose();
  let winding = 0;
  const seen = new Set<string>();
  for (const hit of hits) {
    if (!hit.face) continue;
    const sign = hit.face.normal.dot(ray.ray.direction) >= 0 ? 1 : -1;
    const key = Math.round(hit.distance * 1e6) + ":" + sign;
    if (!seen.has(key)) {
      seen.add(key);
      winding += sign;
    }
  }
  return winding !== 0;
}
