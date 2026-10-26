import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as T from '../../onesa-ai-platform-frontend/apps/chat/node_modules/three/build/three.module.js';
import {GLTFLoader} from '../../onesa-ai-platform-frontend/apps/chat/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
import {solidContainsPoint} from '../../onesa-ai-platform-frontend/apps/chat/src/lib/twin-inspection.ts';
const bytes=fs.readFileSync(new URL('../../onesa-ai-platform-backend/app/twin_fixture_data/pump.glb',import.meta.url));
const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
gltf.scene.updateMatrixWorld(true);
const meshes=new Map();gltf.scene.traverse(m=>{if(m.isMesh)meshes.set(m.userData.twin_component,m);});
const inside=(id,x,y,z)=>solidContainsPoint(meshes.get(id),new T.Vector3(x,y,z));

test('actual flange/cover bores and tangential fluid opening remain empty, surrounded by solid material',()=>{
  for(let i=0;i<8;i++){
    const y=.66+.277*Math.cos(i*Math.PI/4),z=.277*Math.sin(i*Math.PI/4);
    assert.equal(inside('casing',-.9,y,z),false,'casing bolt bore');
    assert.equal(inside('suction-cover',-.936,y,z),false,'mating cover bore');
    assert.equal(inside('cover-gasket',-.9205,y,z),false,'matching gasket bore');
  }
  assert.equal(inside('suction-cover',-.936,.66+.24,0),true);
  for(const y of [.83,.85,.90,1.0,1.24]){
    assert.equal(inside('casing',-.77,y,.27),false,'discharge opens through casing wall');
    assert.equal(inside('discharge',-.77,y,.27),false,'neck is hollow');
  }
  assert.equal(inside('discharge',-.77+.08,1.10,.27),true,'neck retains a real wall');
});

test('axial winding legs occupy real stator slots, and end turns cross teeth outside the core',()=>{
  let slotVertices=0;
  for(const id of ['winding-a','winding-b','winding-c']){
    const m=meshes.get(id),p=m.geometry.getAttribute('position');
    for(let i=0;i<p.count;i++){
      const v=new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(m.matrixWorld);
      if(v.x<.946||v.x>1.414)continue;
      const theta=Math.atan2(v.z,v.y-.66),off=Math.abs(Math.atan2(Math.sin(theta*12),Math.cos(theta*12)))/12;
      const radius=Math.hypot(v.y-.66,v.z);
      assert.ok(off<.075,`${id}: conductor crosses stator tooth at ${v.toArray()}`);
      assert.ok(radius>.128&&radius<.194,`${id}: conductor crosses slot floor or rotor gap`);
      slotVertices++;
    }
  }
  assert.ok(slotVertices>1000,'checks delivered conductor surfaces, not metadata');
  assert.equal(inside('motor-stator',1.18,.66+.175,0),false,'slot seat empty');
  assert.equal(inside('motor-stator',1.18,.66+.17*Math.cos(Math.PI/12),.17*Math.sin(Math.PI/12)),true,'tooth between slots remains solid');
});

test('bearing seats, motor end shields and mounting supports meet delivered housing geometry',()=>{
  const bounds=id=>new T.Box3().setFromObject(meshes.get(id));
  const front=bounds('motor-front-cover'),body=bounds('motor-housing'),back=bounds('motor-back-cover');
  assert.ok(front.max.x>=body.min.x&&back.min.x<=body.max.x,'no detached motor shield gap');
  for(const [race,shaft,x] of [['bearing-inner','coupling-shaft',-.34],['pump-outboard-bearing-inner','coupling-shaft',.07],['motor-de-bearing-inner','motor-shaft',.84],['motor-nde-bearing-inner','motor-shaft',1.52]]){
    assert.ok(bounds(race).min.x<x&&bounds(race).max.x>x);
    assert.equal(inside(shaft,x,.66+.034,0),true,'shaft reaches actual bearing seat');
    assert.equal(inside(race,x,.66+.03,0),false,'shaft bore stays empty');
  }
  for(const id of ['casing','bearing-frame','motor-housing','coupling-guard'])assert.ok(Math.abs(bounds(id).min.y-bounds('base').max.y)<2e-6,`${id}: feet actually contact mounting rail`);
  assert.equal(inside('bearing-frame',-.14,.45,.10),true,'frame feet connect to housing');
  for(const [x,z] of [[-.72,.20],[1.18,.20]])assert.equal(inside('base',x,.12,z),true,'mounting rails beneath feet');
});
