// Offline authoring only. Never imported by the web application or API.
import Module from 'manifold-3d';
import * as T from '../../../onesa-ai-platform-frontend/apps/chat/node_modules/three/build/three.module.js';
import {toCreasedNormals, mergeVertices} from '../../../onesa-ai-platform-frontend/apps/chat/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js';
const wasm = await Module(); wasm.setup();
function solid(geometry) {
  const p=geometry.getAttribute('position'), index=geometry.index, vertices=[], indices=[], mapped=new Map();
  const vertex=i=>{
    const xyz=[p.getX(i),p.getY(i),p.getZ(i)].map(x=>Math.round(x*1e7)/1e7), key=xyz.join(',');
    if(!mapped.has(key)){mapped.set(key,vertices.length/3);vertices.push(...xyz);}
    return mapped.get(key);
  };
  let volume=0;
  for(let i=0;i<(index?.count??p.count);i+=3){
    const ids=[0,1,2].map(j=>vertex(index?index.getX(i+j):i+j));
    if(new Set(ids).size<3)continue;
    indices.push(...ids);
    const [a,b,c]=ids.map(j=>new T.Vector3().fromArray(vertices,j*3));
    volume+=a.dot(b.clone().cross(c))/6;
  }
  if(volume<0)for(let i=0;i<indices.length;i+=3)[indices[i+1],indices[i+2]]=[indices[i+2],indices[i+1]];
  const result=new wasm.Manifold(new wasm.Mesh({numProp:3,vertProperties:new Float32Array(vertices),triVerts:new Uint32Array(indices)}));
  if(result.status()!=='NoError')throw Error('Invalid authored CSG input: '+result.status());
  return result;
}
export function booleanGeometry(union, subtract=[]) {
  const allocated=[];
  try {
    const inputs=union.map(g=>{const m=solid(g);allocated.push(m);return m;});
    let result=wasm.Manifold.union(inputs);allocated.push(result);
    if(subtract.length){const cuts=subtract.map(g=>{const m=solid(g);allocated.push(m);return m;});const cutter=wasm.Manifold.union(cuts);allocated.push(cutter);result=result.subtract(cutter);allocated.push(result);}
    if(result.status()!=='NoError'||result.isEmpty())throw Error('Authored solid boolean failed');
    const mesh=result.getMesh(),g=new T.BufferGeometry();
    g.setAttribute('position',new T.Float32BufferAttribute(mesh.vertProperties,3));g.setIndex(new T.BufferAttribute(mesh.triVerts,1));g.computeVertexNormals();
    const normal=toCreasedNormals(g,Math.PI/5),indexed=mergeVertices(normal,1e-7);g.dispose();normal.dispose();return indexed;
  } finally {for(const m of allocated)m.delete();for(const g of [...union,...subtract])g.dispose();}
}
