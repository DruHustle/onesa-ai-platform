import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import * as T from "../../onesa-ai-platform-frontend/apps/chat/node_modules/three/build/three.module.js";
import { capturePose, descendants, inspectionPose, inspectionAnimationFrame, sectionPlane, solidContainsPoint } from "../../onesa-ai-platform-frontend/apps/chat/src/lib/twin-inspection.ts";
import { validateManifest, validateState, DEFAULT_INSPECTION } from "../../onesa-ai-platform-frontend/apps/chat/src/lib/twin-viewer-contract.ts";
const manifest=JSON.parse(fs.readFileSync(new URL("../../onesa-ai-platform-backend/app/twin_fixture_data/manifest.json",import.meta.url)));

test("authored whole/subassembly poses derive once from immutable baseline and reassemble exactly",()=>{
  for(const motion of manifest.inspection.motions){
    const object=new T.Object3D();object.position.fromArray(motion.pivot);object.rotation.set(.2,.1,-.1);
    const baseline=capturePose(object),scope=manifest.inspection.motions.find(m=>m.component_id===manifest.components.find(c=>c.id===motion.component_id).parentId)||null;
    for(let cycle=0;cycle<1000;cycle++){
      const pose=inspectionPose(baseline,motion,scope,1);
      object.position.copy(pose.position);object.quaternion.copy(pose.quaternion);
      const restored=inspectionPose(baseline,motion,scope,0);
      object.position.copy(restored.position);object.quaternion.copy(restored.quaternion);
    }
    assert.deepEqual(object.position.toArray(),baseline.position.toArray());
    assert.deepEqual(object.quaternion.toArray(),baseline.quaternion.toArray());
    assert.deepEqual(inspectionPose(baseline,motion,scope,-1).position.toArray(),baseline.position.toArray());
    const whole=inspectionPose(baseline,motion,null,1),local=inspectionPose(baseline,motion,scope,1);
    assert.ok(whole.position.clone().sub(local.position).distanceTo(new T.Vector3().fromArray(scope?.translation||[0,0,0]))<1e-10);
  }
  const ids=descendants(manifest,"bearing");assert.ok(ids.size>3);assert.ok(!ids.has("motor"));
});
test("section orientation, position and winding caps preserve actual empty bores",()=>{
  const bounds=new T.Box3(new T.Vector3(-2,-1,-3),new T.Vector3(2,1,3));
  for(const axis of ["x","y","z"]){
    const plane=sectionPlane(bounds,axis,1,false),point=bounds.getCenter(new T.Vector3());point[axis]=bounds.max[axis];
    assert.equal(plane.distanceToPoint(point),0);
    assert.ok(plane.normal.dot(sectionPlane(bounds,axis,0,true).normal)<-.99);
  }
  const torus=new T.Mesh(new T.TorusGeometry(2,.5,16,48));torus.position.set(4,2,-1);torus.scale.set(2,1,1);torus.updateMatrixWorld(true);
  assert.equal(solidContainsPoint(torus,new T.Vector3(4,2,-1)),false,"empty bore stays unselectable");
  assert.equal(solidContainsPoint(torus,new T.Vector3(8,2,-1)),true,"real ring section remains selectable");
  assert.equal(solidContainsPoint(torus,new T.Vector3(14,2,-1)),false);
  torus.geometry.dispose();torus.material.dispose();
});
test("foreign motions, cap scope, duplicate choreography and invalid saved controls fail closed",()=>{
  for(const mutate of [m=>m.inspection.motions[0].component_id="foreign",m=>m.inspection.motions[0].translation[0]=11,m=>m.inspection.motions[0].pivot[0]=1001,m=>m.inspection.motions.push(m.inspection.motions[0]),m=>m.inspection.closed_solids.push("foreign")]){
    const m=structuredClone(manifest);mutate(m);assert.throws(()=>validateManifest(m));
  }
  const state={schemaVersion:"1.0.0",assetInstanceId:"pump-01",selectedComponentId:null,highlightedComponentIds:[],hiddenComponentIds:[],isolatedComponentId:null,transparentSurroundings:false,observations:[],annotations:[],appearance:{theme:"light",locale:"en"},capabilities:{selection:true,annotations:true,statusMarkers:true}};
  for(const patch of [{scope:"foreign"},{explode:1.1},{section_position:Infinity},{section_axis:"q"}])assert.throws(()=>validateState({...state,inspection:{...DEFAULT_INSPECTION,...patch}},manifest));
});

test("inspection reaches exact poses by elapsed time even at low frame rate, excluding prior idle time",()=>{
  assert.deepEqual(inspectionAnimationFrame(0,30),{seconds:0,snap:false});
  assert.deepEqual(inspectionAnimationFrame(16,30),{seconds:.016,snap:false});
  for(const cadence of [16,250,1000]){
    let value=0,now=0,frames=0;
    while(now<600+cadence){
      const step=inspectionAnimationFrame(now,cadence/1000);
      value=step.snap?1:T.MathUtils.damp(value,1,12,step.seconds);
      frames++;if(step.snap)break;now+=cadence;
    }
    assert.equal(value,1,`exact final pose at ${cadence} ms cadence`);
    assert.ok(frames<=Math.ceil(600/cadence)+1);
  }
  assert.deepEqual(inspectionAnimationFrame(-1,NaN),{seconds:0,snap:false});
});
