# ADR 0004: Owned equipment workspace and bounded read-only integration

Date: 2026-10-25. Status: implementation decision; production activation requires release qualification.
Classification: INTERNAL. Owner: AI Platform maintainers.

## Context and inspection

The primary checkout is `onesa-ug/onesa-ai-platform` on dev, clean at inspection.

The starting dev revision is recorded in the branch history and protected evidence index.
Work is isolated on temporary `feature/digital-twin-workspace-20261025`.
The pending Oracle bridge PR remains independent. Company and Robot retain their
independent components and production identities. The established Next.js 16.4.2,
React 19.3 and Python/PostgreSQL stack is retained. Authenticated user ownership
and invitation grants are the existing tenancy boundary; there is no
organization/project membership model to invent.

Existing Industrial investigations are immutable synthetic evidence, not an equipment registry. Knowledge already provides owned extraction/index/retrieval; the tool registry and configured ModelClient remain authoritative. Raw Knowledge binaries are not retained. A model/package therefore needs a new private binary storage adapter, not database text or a disguised Knowledge record.

Accessible Smart Factory components are under sibling `smart-factory-iot/{smart-factory-iot-edge,smart-factory-iot-backend,smart-factory-iot-frontend}`. Its edge contract uses MQTT `factory/{site}/{line}/{device}/telemetry`, millisecond timestamps, device identity and bounded temperature/vibration/pressure/rpm measurements. Reuse that wire contract through an AI-owned read-only adapter; do not import sibling implementation or subscribe to command topics. No live equipment credentials have been established for this feature.

## Decision

The owner's final correction requires strict application independence. All viewer,
validation, fixture generation and application code is maintained directly here.
The uncommitted intermediate shared-package/workspace experiment was removed after
migrating its useful rendering/validation into app-local modules. There is no peer
package, registry, release artifact, handoff or ordered implementation dependency.
Interoperability is optional API/file exchange with explicit external-to-local mappings.

Keep one modular backend and one frontend. Store owner-scoped types/templates, installed equipment, model revisions, original file metadata, signal sources, readings/events and saved workspace records in PostgreSQL. Validated JSONB holds bounded hierarchical metadata; indexed readings remain separate. Templates and model files may be shared within one owner; each installation gets distinct component IDs, serial and measurements. Model revision mappings refer to stable template component IDs and are expanded to installation IDs. Never infer identity from names or array positions.

Use a private content-addressed disk adapter on an explicitly configured durable local development directory. An enabled hosted pilot requires an operator-provisioned persistent mount; missing storage is a scoped Digital Twins readiness failure, not a failure of Chat. File access always resolves an owned database record first. No URL fetching, public file URL, automatic CAD conversion or temporary deployment disk fallback.

Use exact-pinned MIT Three.js 0.186.1 and React Three Fiber 9.8.2 (React >=19 <19.4). Browser-only dynamic loading and demand rendering keep the engine out of ordinary Chat. Use Three's GLTFLoader and OrbitControls, no extra engine or optional Drei dependency. Accept bounded embedded GLB 2.0 without external resources/extensions for this pilot. Preserve unsupported source attachments without claiming they render. AAS 3.0 JSON and AASX 3.0 packages use maintained BaSyx 2.2.0 after bounded safe package preflight; 02026 1.0 is an interoperability reference, not a full conformance claim. Preserve original packages and unknown submodels.

MQTT 3.1.1 via pinned paho-mqtt 2.1.0 feeds a source-scoped token ingestion endpoint. Browser sessions retain existing Origin/CSRF. Source tokens are hashed, revocable and never grant retrieval. Batches are bounded, serializable per asset, deduplicated and ordered by observation time. Late samples remain in history but cannot change current state or emit current threshold transitions. Replay cannot change live alarms. Polling resynchronizes complete bounded state; browser never holds MQTT credentials.

Equipment tools reauthorize each resource through existing user sessions, return deterministic facts and owner-filtered Knowledge evidence, and can be registered in the existing agent runtime. Model commentary is separately labeled and cannot mutate state or execute viewer code. Only allowlisted component actions are accepted. Saved inspection reports retain evidence snapshots. The versioned robotics view uses current platform authentication; no shared SSO, actuation, collision/kinematics or new Robot runtime is implied.

## Implementation plan

1. Add migration, validated domain/storage/import modules and ownership/readiness gates. Generate reproducible self-authored pump GLB, AAS/AASX and manual fixtures.
2. Implement setup/import preview/commit, per-revision mappings, documents, bounded telemetry/history/thresholds, scoped tools, reports and robotics view.
3. Build accessible responsive workspace, lazy 3D interaction and useful graphics fallback. Preserve system CSS themes and existing application navigation.
4. Exercise isolated PostgreSQL, actual local MQTT and actual browser journeys, including foreign-owner access, malicious imports, model replacement and persisted reports. Measure demo performance on the observed local environment.
5. Regenerate contracts, update maintained user/engineering references, run required checks, commit/push a reviewable feature PR to dev. Qualify staging only through established source-bound authority. Keep production flags and independently deployed components unchanged until separately qualified.

## Consequences

The first slice supports investigation, not numerical simulation, drawing reconstruction, factory authoring, validated predictive maintenance, immersive training or physical control. Unit and coordinate provenance travel with models; a visualization mesh is not planning geometry. Bounded core-format support deliberately rejects unsupported rendering features rather than loading untrusted remote decoders or assets. Hosted storage and real equipment acceptance remain explicit operational checks.

References: [R3F compatibility](https://r3f.docs.pmnd.rs/getting-started/introduction), [Three.js](https://threejs.org/docs/), [glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html), [IDTA specifications](https://industrialdigitaltwin.org/en/content-hub/aasspecifications), [02026 1.0](https://github.com/admin-shell-io/submodel-templates/tree/main/published/Provision%20of%203D%20Models/1/0), [BaSyx](https://github.com/eclipse-basyx/basyx-python-sdk).
