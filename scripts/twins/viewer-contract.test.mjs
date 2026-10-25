import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {validateManifest, validateState, validateCommand, validateEvent, inspectGlb} from "../../onesa-ai-platform-frontend/apps/chat/src/lib/twin-viewer-contract.ts";

const directory = new URL("../../onesa-ai-platform-backend/app/twin_fixture_data/", import.meta.url);
const manifest = JSON.parse(fs.readFileSync(new URL("manifest.json", directory)));
const state = {schemaVersion:"1.0.0",assetInstanceId:"pump-01",selectedComponentId:"bearing",highlightedComponentIds:[],hiddenComponentIds:[],isolatedComponentId:null,transparentSurroundings:false,observations:[],annotations:[],appearance:{theme:"light",locale:"en"},capabilities:{selection:true,annotations:true,statusMarkers:true}};
test("Onesa-owned fixture manifest and embedded GLB have matching nodes and bounds", () => {
  const checked = validateManifest(manifest), bytes = fs.readFileSync(new URL("pump.glb", directory));
  const result = inspectGlb(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));
  assert.equal(result.nodes.length, 5); assert.equal(result.triangles, 480);
  assert.deepEqual(new Set(result.nodes), new Set(checked.mappings.map(m => m.sceneNode)));
});
test("model versions, units, hierarchy and explicit mappings fail closed", () => {
  for (const mutate of [m => m.schemaVersion="2.0.0", m => m.metersPerUnit=0.001, m => m.mappings[1].sceneNode=m.mappings[0].sceneNode, m => m.mappings[0].componentId="foreign", m => m.components[0].parentId=m.components[0].id, m => m.artifact.byteLength=50000000, m => m.transform[15]=0]) {
    const candidate=structuredClone(manifest); mutate(candidate); assert.throws(() => validateManifest(candidate));
  }
});
test("state and structured actions cannot cross an installed asset or model boundary", () => {
  assert.equal(validateState(state,manifest).observations.length,0);
  assert.throws(() => validateState({...state,selectedComponentId:"foreign"},manifest));
  assert.throws(() => validateCommand({schemaVersion:"1.0.0",action:"execute_javascript",code:"alert(1)"},manifest));
  assert.throws(() => validateCommand({schemaVersion:"1.0.0",action:"focus_component",componentIds:["foreign"]},manifest));
  assert.deepEqual(validateCommand({schemaVersion:"1.0.0",action:"highlight_components",componentIds:["bearing","motor"]},manifest).componentIds,["bearing","motor"]);
  assert.throws(() => validateEvent({schemaVersion:"1.0.0",type:"component_selected",assetInstanceId:"pump-02",componentId:"bearing"},state,manifest));
});
test("missing, stale, bad and replay inputs are explicit rather than healthy zeros", () => {
  const observation={componentId:"bearing",metric:"vibration",value:null,unit:"mm/s",observedAt:null,ingestedAt:null,sourceId:"fixture",quality:"unknown",freshness:"unknown",connection:"disconnected",mode:"simulated",status:"unknown"};
  assert.equal(validateState({...state,observations:[observation]},manifest).observations[0].value,null);
  assert.throws(() => validateState({...state,observations:[{...observation,status:"normal"}]},manifest));
  assert.throws(() => validateState({...state,observations:[{...observation,value:NaN}]},manifest));
});
test("standalone source has no custom shared SDK or peer configuration requirement", () => {
  const app = new URL("../../onesa-ai-platform-frontend/apps/chat/", import.meta.url);
  const packageJSON=JSON.parse(fs.readFileSync(new URL("package.json",app)));
  for (const [name,version] of Object.entries({...packageJSON.dependencies,...packageJSON.devDependencies})) {
    assert.ok(!name.startsWith("@onesa/equipment")); assert.ok(!String(version).match(/file:|git\+|smart.factory/i));
  }
  const renderer=fs.readFileSync(new URL("src/components/twin-canvas.tsx",app),"utf8");
  assert.ok(!renderer.match(/fetch\(|\/api\/|mqtt|smart.factory|@onesa\/equipment/i));
  const root=JSON.parse(fs.readFileSync(new URL("../../onesa-ai-platform-frontend/package.json",import.meta.url)));
  assert.equal(root.workspaces,undefined);
});
