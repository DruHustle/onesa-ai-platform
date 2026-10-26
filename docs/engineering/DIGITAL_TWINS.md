# Digital Twins

Classification: INTERNAL. Owner: Onesa AI Platform maintainers. Contract: v1.
Implementation candidate: 2026-10-25; hosted acceptance and production activation are separate release gates.

Independently pinned viewer dependencies are Three.js 0.186.1, React Three Fiber 9.8.2
and Zod 4.6.7, with development types 0.186.0. Backend import/adapter dependencies are
BaSyx 2.2.0, defusedxml 0.7.1 and paho-mqtt 2.1.0. Existing platform versions and locks
remain authoritative; none of these dependencies belongs to another application.

## Ownership and independent startup

The route is `/industrial/twins` inside Industrial AI. Onesa owns its React renderer,
local validation, model originals, PostgreSQL records, authenticated file delivery,
documents, readings and saved work. No Smart Factory server, account, database, package,
registry, artifact, prior pairing or startup order is required. Company and Robot are
independent products and receive no actuation or database dependency.

The superseded shared-package experiment was uncommitted: three custom package
directories, a frontend workspace declaration and its new root lockfile. Useful renderer
and validation code were migrated into `apps/chat/src/components/twin-{viewer,canvas}.tsx`
and `src/lib/twin-viewer-contract.ts`; package/workspace configuration was removed.
There is no custom viewer/schema SDK to publish, install, synchronize or hand off.
The fixture generator is `scripts/twins/generate_fixtures.py`; its checked-in, hashed
outputs belong to `backend/app/twin_fixture_data`. These are Onesa assets, not a peer
release. Private draft evidence is excluded from source and both Docs builds.

Required development dependencies are Node 24, Python 3.11, Docker/Compose, this
repository's locks, and the existing PostgreSQL/pgvector service. From a clean checkout:

```sh
python3 scripts/bootstrap_env.py
docker compose -f compose.yaml -f compose.twins-demo.yaml up --build --wait
make install
npm --prefix onesa-ai-platform-frontend/apps/chat ci
```

Open the configured Chat origin (default `http://localhost:3100`), register/sign in using
the existing local account flow, open Industrial AI · Digital Twins, and explicitly
load the isolated pump demonstration. The overlay enables only a development pilot,
adds a private persistent model volume and an authenticated loopback MQTT fixture.
It must never be applied to production Compose. It creates no account or customer
equipment automatically. Stop with the same two `-f` arguments and `down`; retain volumes.

Ordinary `make up` preserves default-off Twin exposure. An unconfigured optional
connector does not participate in startup, login, core readiness or model loading.
Readiness requires schema `20261025_twins` only when Twins is enabled; ordinary features
remain compatible with their retained earlier schemas. `/api/v1/twins/readiness` reports
the scoped storage dependency separately from model inference and optional conversion.

## Setup and investigation

Create a reusable equipment type/template, then a named installed instance with a serial.
Alternatively preview an AAS package and explicitly commit one equipment instance.
Embedded TXT/PDF manuals can be explicitly indexed into owned Knowledge during commit.
Preserved attachments remain downloadable and indexable from Documents after reload;
omitting indexing does not lose originals or prevent local 3D inspection.
Attach a prepared model, review every scene-node mapping and scale, link/index a TXT/PDF
manual, configure a signal source, preview, and activate. Setup progress persists with
optimistic revision checks. Two demo pumps share geometry/template while retaining
distinct installed component IDs and separate measurements, notes and history.

Select using the component list or 3D view. Orbit, pan, zoom, fit/reset, focus,
hide/show, isolate and surrounding transparency operate on actual model geometry.
Annotations and viewpoints persist as owned records. Details remain accessible through
lists/tables when graphics are unsupported or context is lost. Model preparation is
independent of bounded five-second state polling; scene resources are disposed on
replacement/navigation. CSS system preference controls appearance; there is no stored
theme override. Readings are never used to animate a fictional physical simulation.

The self-authored reference v2.1 is an illustrative end-suction pump and TEFC motor,
right-handed Y-up in meters. Its 68-item hierarchy has 61 selectable geometry parts
and seven logical subassemblies. It includes a growing volute/empty fluid passage,
shrouded curved-vane impeller, shaft/sleeve, ceramic/carbon/elastomer mechanical seal,
four bearings with races/rolling elements/open cages, flexible coupling, finned motor,
slotted stator, copper winding assemblies, slotted rotor packs/conductor cage, fan,
vented covers and fasteners. This is no manufacturer CAD or certified maintenance design.

The viewport comes before advanced inspection and local-simulator controls; mobile
Model places the viewport before the BOM. Use Explode/Reassemble or the continuous
0–100% slider. Open Section, subassembly and reveal controls below the viewport. Whole-assembly motions are
authored, not random radial displacement. Select an assembly in Explosion scope for
relative subassembly separation; Isolate and Focus selected reveal its internals.
Every pose derives from an immutable baseline, with authored offsets/rotations/pivots;
logical parent transforms are never applied again to children. Reduced motion snaps
to the same targets. Guide lines and bounded selected/assembly labels are optional.

Section controls provide X/Y/Z axes, position, reversal, solid cut faces and reset.
Reverse the direction to remove the side facing the camera. Per-part nonzero-winding
stencils retain holes and cavities; server-side edge/winding audits reject cap claims
for open or inconsistently oriented meshes. The open-ended seal spring is deliberately
uncapped. Cap picking checks actual solid winding instead of selecting an infinite
plane across a bore. Ghost housings are transparent and uncapped; Hide covers and
Restore all support internal inspection. These reveal existing modeled geometry only.

Saved viewpoints bind the model revision, camera, explosion/scope, section settings,
labels/guides, housing ghosting, hidden/isolate/transparency state and installed part.
Views against a different active revision remain retained but cannot silently apply.
The BOM exposes each part's modeled/combined status, material appearance and intentional
simplifications in Details. Seed v2 uses distinct template/instance identities and does
not overwrite earlier v1 demo records. Add detailed reference upgrades by adding v2. Gray markers
mean unknown, amber indicates a declared threshold rule, and stale/bad quality remains
explicit in the textual details. Missing observations are null/unknown rather than zero.

History is an end-exclusive window of at most seven days, bounded to 500 observations
and 200 events. Truncated results are labeled; narrow the window. Replay reads/writes a
separate dataset and never changes live current state, connectivity or alarms.

## Reproducible source and rights

`node scripts/twins/author_reference.mjs OUTPUT_DIRECTORY` authors GLB, BOM/motions and
surface audit using this app's pinned Three.js. The offline solid-authoring dependency is Manifold 3.5.4 (Apache-2.0), locked separately under `scripts/twins/solid-tools`; install it with `npm ci --ignore-scripts --prefix scripts/twins/solid-tools`. It is an ordinary third-party library, never an application/peer package. It is not installed in API or browser images. After both tool installs, run
`.venv/bin/python scripts/twins/generate_fixtures.py` to regenerate the complete hashed
GLB/AAS/AASX/manual fixture package. No asset download, sibling code or peer artifact
is involved. Parametric JavaScript is the editable native source; the GLB is its viewing
derivative. The model is self-authored Onesa material under repository ownership; no
manufacturer marks, borrowed CAD or new third-party asset license is represented.

The declared mechanical scope intentionally combines rolling-element sets, rotor
lamination packs, winding bundles and fastener head/washer/shank assemblies. Exact
thread helices, individual wire strands and individual thin steel sheets are omitted
with explicit per-component inventory notes. Terminal electrical internals/cables and
CFD are outside this mechanical reference. The maintenance document sections 4–5
explain inspection and the BOM limitations. No unavailable major mechanical interior
is silently replaced with a texture or exterior shell.

Reference 2.1 corrects the cast passage opening, drilled mating flange/gasket bores,
shaft/sleeve/bearing seats, connected supports, end-shield fit, coupling jaws/insert
and conductor placement. Offline solid booleans remove overlapping internal faces;
the viewing derivative retains all 61 selectable geometry identities. The delivered
winding legs occupy actual core slots, and end turns cross teeth outside the core.
Geometry tests check the actual delivered surfaces/bores and seat relationships.
These checks do not certify dimensions, clearances, flow or an electrical winding.
Keyway/retention details, exact threads, individual wire strands and sheets remain
illustrative simplifications, rather than validated service or installation geometry.

The source template namespace/component IDs remain stable. Existing equipment keeps
its original model, files, documents, signals and saved views when the fixture source
changes. A fresh demonstration uses reference 2.1. To adopt a new derivative on an
existing installation, attach it through Equipment setup, explicitly review its node
mapping and activate that new revision. Old saved views remain revision-bound; the
seed action never silently replaces an existing active model.

Generic GLB/AAS imports retain supplied surfaces/provenance and explicit node mappings.
The supported AAS file profile does not infer an assembly/BOM or choreography from names;
flat imported mesh components are honest about lacking authored explosion/cap metadata.
The fully authored local template retains its own reviewed hierarchy and motions.

## Storage and data model

`digital_twins_enabled` defaults false. `digital_twins_demo_enabled` defaults false and
cannot seed production. `digital_twins_storage_directory` must be an absolute, private
mode-0700 directory. Development may use a durable local directory; hosted activation
also requires explicit `digital_twins_persistent_mount=true` after an operator verifies
the mounted volume, ownership, backup and recovery. This declaration is not a storage
durability proof. Never select ephemeral Vercel/container storage as a substitute.

The model volume is owned by runtime UID 10001 in the local container. Files are
content-addressed within a private owner UUID namespace, mode 0600, atomically created,
fsynced and hash-checked on reads. An owned database record must authorize each download.
Files are not public URLs or database text. Preserve the volume alongside database
backups. Failed database transactions can leave inaccessible content-addressed orphans;
inspect against owned `twin_files` records before any separately authorized cleanup.

Tables: `twin_templates`, `twin_assets`, `twin_files`, `twin_models`, `twin_sources`,
`twin_readings`, `twin_events`, `twin_notes`. Reuse the platform's authenticated user
and current invitation grant boundary; no organization membership is invented.
Template component UUIDs are stable across model revisions. Installed component UUIDs
belong to one asset. A model revision stores an explicit node-reference to template
component mapping. Scene names and `node:N` references are revision-local hints, never
durable equipment identity. Replacement requires complete explicit mapping and review.

Source packages retain hashes, original bytes, preserved AAS environment, unsupported
elements, attachment paths and source-to-local asset identity mapping. The local pump
records an explicit source component-role to local template UUID mapping. External
sources store external-system/asset/component mappings separately from local IDs.
Sync may add observations through that reviewed mapping; it cannot rename local assets,
replace models, change annotations/rules or delete history. Unsupported versions and
unmapped tags/components fail closed. No direct peer database or storage access exists.

Capacity is bounded: 100 installed assets, 100 templates, 200 file/model records,
100 MiB file metadata quota per owner, 20 sources per asset, 32 bindings per source,
1,000 notes per owner and 100,000 readings per asset. Ingestion accepts observations
within 30 days; capacity exhaustion rejects new data explicitly. There is no automatic
production history deletion. Configure an owner-approved retention/export procedure
before enabling real processing; preserve privacy deferrals. Account export includes
owned Twin metadata/evidence even when disabled and excludes source token hashes.
Binary originals use separately authorized downloads. Existing export byte/row ceilings
remain. Password-confirmed account deletion includes owned files and FK-cascaded records.

## Supported files and safety

Browser uploads are at most **4 MiB**, below the existing Vercel gateway request limit.
GLB 2.0 is the viewing format. This pilot accepts static untextured embedded core
triangle meshes, at most 100 nodes, 100,000 triangles and 200,000 VEC3 accessor entries
(including normals). Skins, animation, textures and extensions/remote decoders are
rejected with a preparation message. External buffers/images are never fetched.
Model bytes, hash, transforms, scene reachability and mappings are validated before use.

This ceiling is a small equipment-inspection pilot, not a general manufacturer-CAD
viewer. Reference 2.1 uses 97,054 triangles (97.0% of the ceiling) and 2,779,092 bytes
(66.2% of the file ceiling). Larger/textured assemblies remain unsupported. The
measured preparation improvement here is an Onesa-owned offline viewing derivative:
editable parametric solids, real boolean openings/unions, bounded curve tessellation
and stable per-part mappings. It fits the existing gateway and validation profile
without deleting major internals or adding a network decoder. It is not a generic
CAD converter or automatic simplifier. Preserve source/native originals and their
hashes in approved engineering custody; a file rejected by the upload boundary has
not been retained by the app. Do not send larger payloads through the Vercel gateway.
STEP/drawing preservation below is attachment support, distinct from rendering.
STEP/STP, drawings (PDF/PNG/JPG) and TXT can remain original source attachments; this
does not render CAD or reconstruct geometry. No automatic converter is installed.

AAS **3.0 JSON** and the **AASX 3.0 JSON-environment profile** are parsed with pinned
BaSyx 2.2.0. Tests cover the generated package with embedded GLB/manual and missing/external
geometry. AAS XML environments, multi-shell/multi-environment packages and unsupported
versions are rejected. IDTA 02026 1.0 `Models3D` is an interoperability reference; the
illustrative fixture is not a claim of full 02026/AAS conformance. Semantic references,
properties, file references and unknown content survive import. Missing geometry stays
missing until a prepared model is attached; no registry is needed.

ZIP preflight limits entries to 100, expanded bytes to 20 MiB and expansion ratio to
100:1. Traversal, symlinks, duplicate entries, encrypted archives, DTD/entities and
external OPC relationships are rejected. No archive path is extracted to the filesystem.
Metadata URLs are displayed as provenance, never fetched automatically. PDF extraction
reuses the existing bounded Knowledge parser/isolation pipeline.

## Read-only telemetry and optional interoperability

`POST /api/v1/twins/assets/{asset}/sources` is an authenticated owner/CSRF operation.
It returns one scoped ingestion credential once. Store it in private edge configuration;
it is never bundled, placed in URLs, persisted in browser storage, logged or exported.
MQTT credentials stay on the edge. Source credentials permit ingestion only, are hashed,
revocable, and recheck the account's current eligibility. They cannot retrieve equipment,
files or history. Robotics v1 uses existing Onesa session/grant authentication; no Robot
SSO, new IdP or token-based read access is assumed.

`POST /api/v1/twins/sources/{source}/readings` takes `X-Onesa-Source-Token` and a v1
`{mode, samples}` body, at most 100 samples. Each sample has immutable message ID, tag,
finite numeric value/unit, timezone-bearing observation timestamp and quality. Source
binding determines the local installed component; client tenant fields are rejected.
The database stores observation and ingestion times, original value/unit, conversion
and external provenance. Compatible conversions are K/Cel, Pa/bar and m/s/mm/s. Vibration
means velocity here; acceleration is not silently relabeled or converted. Unknown
metric meanings require review. Same-identity/same-content deliveries deduplicate;
conflicting identities are rejected. Asset/source locks serialize concurrent ingestion.
Late samples remain in history without replacing newer current state or emitting
retrospective current alarms. Threshold recovery uses the configured hysteresis.

The optional app-local MQTT adapter understands the documented `factory/{site}/{line}/
{device}/telemetry` wire subset: deviceId, epoch-millisecond timestamp and configured
top-level numeric metrics. It subscribes only to an exact telemetry topic, never command
topics. The operator chooses each metric's tag/unit. No physical sensor/unit equivalence
is inferred from a matching label. Smart Factory is one possible producer; its separate
proposed fan-out schema is not silently accepted or claimed compatible. It must translate
through reviewed local source/component mappings or undergo a future explicit adapter.

Run with a mode-0600 operator JSON file and environment-held credentials:

```sh
cd onesa-ai-platform-backend
../.venv/bin/python -m app.twin_mqtt /absolute/private/adapter.json
```

Configuration fields and validation live in `app/twin_mqtt.py`. Remote MQTT/API endpoints
require verified TLS; plaintext is restricted to loopback fixtures. MQTT uses persistent
sessions/QoS and the platform's idempotent IDs. Transient API failures leave messages
unacknowledged, with bounded reconnect backoff. The producer/broker owns its bounded
durable queue; configure its policy before any real equipment acceptance. No external
source is contacted merely because Twins is enabled. Source freshness/connectivity
derives from last observation/ingestion and the reviewed stale policy, not a claim of
physical machine health. Stopping an optional producer leaves local models, manuals, annotations, history, other sources and deterministic tools available.

The app-owned simulator also operates with no broker or external integration. In the
explicit pilot, select a component and use **Run local simulated cycle**, normal/alarm/
recovery, or **Pause local simulated source**. Its owner/CSRF endpoint writes only a
separate simulated dataset. A paused simulator is explicitly labeled; it never
impersonates a disconnected live feed.

The protocol fixture additionally uses an actual local broker → Paho adapter → authenticated API
workflow, not a random browser animation. The UI creates a simulated vibration source
for the selected bearing; `app.twin_mqtt_fixture` receives that source ID/credential on
stdin and publishes normal, threshold, hysteresis and recovery samples. Stop publication
to observe stale/disconnected. Broker test credentials are explicitly disposable and
are not production credentials. Real equipment/source acceptance remains unverified.

## Equipment tools, reports and Robot boundary

The existing tool registry exposes `equipment_evidence_v1`, rechecking current session,
grant, asset and component on every call. Current readings come from telemetry, not
embeddings. Retrieval is restricted to associated owned Knowledge documents. Results
identify equipment/serial/component, time window, mode, units, timestamps, quality,
bounded rule events and document chunks. Imported instructions are untrusted evidence.
Model commentary uses the existing provider and capacity controls; no new training,
provider fallback or Smart Factory AI call exists. Mock, unavailable/invalid, deterministic
evidence and model-backed unconfirmed hypotheses are distinct. Quotes must be present
in the source excerpts actually sent to the model. The provider receives a separate
24,000-character evidence selection, preserving recent observations and labeling its
incompleteness; the complete owned tool response and saved snapshot are retained.
No threshold rule proves a cause or predictive maintenance.

Only structured `focus_component` / `highlight_components` actions with owned component
IDs are accepted by the API. No generated JavaScript or machine command is executed.
Inspection checklists persist immutable evidence snapshots/checksums and citations.
Periodic asset detail responses contain report summaries rather than full observation
snapshots; the authenticated saved-note endpoint provides the complete original snapshot.
`GET /api/v1/twins/assets/{id}/robotics/v1` exposes local IDs, relationships, model revision,
units/frame/transform and operating state. Visualization geometry is explicitly not
collision geometry, calibrated kinematics, a planning environment or actuation.

## Verification and release

```sh
node --test scripts/twins/viewer-contract.test.mjs scripts/twins/inspection.test.mjs scripts/twins/mechanical.test.mjs
make check
make openapi api-client contract-check
make frontend-check
ONESA_BROWSER_URL=http://localhost:3100 npm --prefix onesa-ai-platform-frontend/apps/chat run test:e2e -- tests/twins.spec.ts
```

Browser fixtures are loopback-only and use disposable accounts. MQTT verification uses
the locked host `.venv` and overlay broker. Required CI retains its existing checks and
adds the same local feature tests, without provider credentials or peer checkout access.
Linux Firefox uses its headed renderer under Xvfb because the observed stock headless
runner disables WebGL 2. Chromium/WebKit retain their headless coverage. No browser
security preference or application graphics fallback is changed to pass the checks.
Retained screenshots/results belong in ignored `data/` or the existing protected evidence
index. Cold tests use fresh browser storage, deny non-Onesa application destinations,
and inspect requests. Source-outage tests stop/block the isolated producer, keep Onesa
running, and verify stale status plus local model/history/document/report continuity.
Do not stop another project's running services for these tests.

Performance budget: 2,779,092-byte/97,054-triangle detailed local reference; at most 100,000 triangles for
accepted user models; DPR at most 1 on narrow viewports and 1.5 otherwise; demand rendering,
no continuous frame-rate telemetry updates. Measure model transfer/parse and first actual
render separately on a named observed device/browser/network. Loopback or software WebGL
results are not physical-device or hosted network benchmarks. Record failures and unsupported
graphics honestly; a loaded component or screenshot alone does not establish the full flow.

Observed reference check on 2026-10-26: Mac15,13, Apple M3, 24 GiB RAM;
production Docker build, fresh browser contexts, loopback delivery, viewport/DPR
1440×1000/1 and 390×844/1. PCF shadows, antialiasing, stencil and the 64-pixel room
prefilter stayed enabled. No major interior or inspection feature was removed.
The final GLB SHA256 is
`114320d3f1b48fa11f46b8681bb360ae8c79d85c02b032030482ce0b6ac102de`.
Browser versions were WebKit 27.2 and Chromium 156.0.8078.4. These are local samples,
not hosted-network or physical-phone acceptance. Other users' host workloads were
preserved. The protected evidence records exact source and configuration identities.

`scripts/twins/profile.mjs PRIVATE_OUTPUT_DIRECTORY webkit` (or `chromium`) is an
explicit loopback-only experiment after starting the production build. It creates
and password-deletes one disposable account, blocks non-owned origins and checks
that cold ordinary Chat has no canvas or registered Three engine. Each state has
2 seconds warm-up and 8 seconds sustained browser-rAF-driven input. No per-frame
automation round trip or `gl.finish()` is used. The samples below are render-completion
callback intervals, **not native FPS, GPU duration or presentation latency**. Section
inputs are dispatched at most every 50 ms, and repeated rounded values require no
new frame; their intervals therefore include that input cadence. Discrete tails are
not proof of GPU stalls. CPU submission is sampled separately.

| Renderer / width | Assembled orbit median / p95 ms | Explosion median / p95 ms | Section movement median / p95 ms | Ghost orbit median / p95 ms | Winding close-up median / p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| WebKit / Apple GPU / 1440 | 17 / 19 | 17 / 21 | 51 / 102 | 17 / 19 | 17 / 19 |
| WebKit / Apple GPU / 390 | 17 / 18 | 17 / 22 | 51 / 71 | 17 / 19 | 17 / 19 |
| Chromium / SwiftShader / 1440 | 86.8 / 119.5 | 85.9 / 115.8 | 134 / 233.2 | 116.9 / 146.2 | 17.5 / 25.2 |
| Chromium / SwiftShader / 390 | 72.9 / 112.1 | 58.4 / 78.8 | 116.7 / 162.4 | 97.6 / 131.4 | 16.7 / 18.6 |

Fully exploded orbit was 17.0/19.0 ms on Apple GPU at 1440,
and 17.0/18.0 ms at 390. SwiftShader measured
63.7/84.8 and 52.5/67.3 ms respectively.
Each distribution's sample count and raw observations are retained in the private
packet. Software full-assembly interaction is visibly slower and does not qualify
accelerated-desktop or mobile performance. Lists, details and deterministic evidence
remain available on unsupported/slow graphics. Physical-phone qualification remains
pending; viewport emulation is not hardware.

Cold transfer / hash-and-geometry validation / GLTF parse was 64.00/2.00/6.00 ms on WebKit,
and 31.60/3.90/7.30 ms on Chromium. First actual settled render was 241/269 ms. Total
preparation also includes mapping/material setup and is reported separately by the
viewer, rather than attributed entirely to parsing. These are single cold-load
observations, not percentile estimates.

The delivered scene uses 125 draw calls assembled, including shadows; section
movement reached 272, and isolated windings used five. Median CPU submission was
0–2 ms on Apple GPU and 0.1–1 ms on SwiftShader, with higher section cost recorded
in the full sample. Geometry allocations remained at 64 before first section and
65 afterward; textures stayed at four. Shader program count rose from five to eleven
as section/ghost variants were first used, then remained bounded. The profiler
retains these counts and available browser heap samples; heap snapshots alone are
not a leak proof. Tests separately verify route-unmount context/resource cleanup.
Settled scenes rendered only two additional frames in each 12-second interval,
spanning five-second data polling, rather than a continuous idle loop.

The earlier eight-sample, automation-plus-`gl.finish()` figures belonged to reference
2.0 and are retained in the historical private packet. They are not transferred to
this derivative or used as native FPS evidence.

Review captures include assembled, whole/subassembly explosion, hollow-bearing cut
faces, longitudinal cutaway, ghost housings, isolated stator/impeller/winding/rotor
close-ups, both appearances and mobile viewport controls. Tests exercise moved-part
picking, exact baseline restoration, saved view/source bindings, actual API restart
and three route unmount/remount cycles with old WebGL context loss. Per-part bounded
cap patches avoid full-screen overdraw. The broad-panel room lighting uses a bounded
64-pixel procedural cube prefilter; no external HDR texture is fetched. First-frame
browser assertions allow the bounded software shader setup while still requiring an
actual nonzero rendered frame. DPR and source complexity remain capped.
Repeated shapes are merged within explicitly declared selectable BOM sets; no new
remote decoder, texture service or identity-destroying shell fallback is introduced.

Promote reviewable source through dev → staging → main with exact-source CI, isolated
staging, genuine owner-run authorization and actual hosted verification. Production flags
and existing independently deployed components remain unchanged until separately qualified.
Back up DB and file mount together; migrate before enabling. Roll back by disabling Twins
and reverting the independently qualified frontend/API artifacts while retaining the additive
schema and files. Destructive downgrades are intentionally rejected. No automatic publication,
new provider account, billing/visibility change or real-data activation follows from these changes.

Deferred: numerical simulation, engineering-accurate drawing reconstruction, full factory
authoring, validated predictive models, immersive training, conversion workers and physical
actuation. This implementation does not advertise those as available.

### Transition timing correction

Inspection transitions use elapsed active wall time from the latest explosion/scope
request and copy the exact authored target on the next rendered frame after 600 ms.
Prior idle time is excluded. This avoids an indefinite animation tail on slow renderers;
reduced motion still snaps immediately and settled scenes return to demand rendering.
The regression delays actual browser frames by 750 ms and preserves the existing
five-second settling assertion. This is a deterministic scheduling test, not a device
performance benchmark. Earlier measured profiles remain historical observations of
source 8bb4. The table above was refreshed against application source
`91b1507481c0f64d3663a8f9f375bf4ad5f5e249` with the corrected elapsed-time transition.
Both raw profiles retain the exact source, model and functional file hashes plus
the profiling-harness working-diff hash. The harness observes actual ordinary-Chat
startup responses and a visible composer before a 500 ms Chat settle window; it
does not make a disabled optional endpoint or global network-idle heuristic a
viewer prerequisite. Model timing begins only when the owned model is requested.
Browser exceptions retain their phase and message and prevent a successful profile;
failed intermediate runs remain private evidence. Neither this measurement nor
application-byte equivalence transfers release authorization to a later commit.
Physical-phone qualification and exact-source hosted release acceptance remain
separate pending checks in the protected packet.

The AI-only `infra/deployment/oracle-private-twins.compose.yaml` overlay adds only
explicit private host binds and refuses to create missing host paths. It does not
enable Twins. The owner provisions separate UID/GID10001 mode0700 staging and
production directories, validates the full root-owned Compose identity, coordinates
DB/file backups and applies the additive schema before separately authorized
activation. Existing ports, ingress, credentials and other workloads are preserved.

### Read-only Robot context export

The equipment workspace downloads its existing owned `robotics/v1` response as
JSON through the current authenticated AI session. Export always retains the live
source provenance, including when the viewer displays a simulated mode. It sends
no request to Robot and supplies no shared operator authority. Robot optionally
imports a bounded file with explicit tag mapping, P-101 reference units and an
immutable approval-bound snapshot; its default configuration keeps import off.
No service credential exchange, factory write, hardware command or live acceptance
is implied by a file export. Empty or stale live evidence remains empty or stale.
