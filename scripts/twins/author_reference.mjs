/**
 * Onesa-authored illustrative end-suction pump / TEFC motor reference.
 * Editable parametric source; no vendor CAD, external asset or peer service.
 * Values describe this reference's proportions, not manufacturer dimensions.
 */
import * as T from "../../onesa-ai-platform-frontend/apps/chat/node_modules/three/build/three.module.js";
import { mergeGeometries, mergeVertices, toCreasedNormals } from "../../onesa-ai-platform-frontend/apps/chat/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js";
import { GLTFExporter } from "../../onesa-ai-platform-frontend/apps/chat/node_modules/three/examples/jsm/exporters/GLTFExporter.js";
import fs from "node:fs";
import { booleanGeometry } from "./solid-tools/solids.mjs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const output = process.argv[2] || path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../onesa-ai-platform-backend/app/twin_fixture_data");
fs.mkdirSync(output, { recursive: true });
// GLTFExporter uses this standard browser interface only to package embedded buffers.
globalThis.FileReader = class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(value => { this.result = value; this.onloadend?.(); }); }
  readAsDataURL(blob) { blob.arrayBuffer().then(value => { this.result = "data:application/octet-stream;base64," + Buffer.from(value).toString("base64"); this.onloadend?.(); }); }
};
const scene = new T.Scene(), components = [], motions = [], groups = new Map(), topology = {};
const material = (name, color, metalness, roughness) => new T.MeshStandardMaterial({ name, color, metalness, roughness });
const materials = {
  paint: material("Indigo enamel / cast housing", "#344f91", .42, .3),
  motor: material("Slate blue enamel / aluminium housing", "#35465c", .58, .31),
  steel: material("Machined steel", "#a4adb7", .88, .24),
  darkSteel: material("Dark steel / laminations", "#58616b", .82, .31),
  stainless: material("Stainless impeller / sleeve", "#c6cbd1", .91, .21),
  copper: material("Copper windings and rotor cage", "#b86732", .86, .28),
  brass: material("Bearing cage / brass", "#b39149", .8, .27),
  rubber: material("Elastomer seal / gasket / coupling insert", "#20252a", .02, .64),
  ceramic: material("Ceramic seal seat", "#dadac8", .12, .21),
  carbon: material("Carbon mechanical-seal ring", "#3d4146", .14, .47),
};
const Y = .66;
function tidy(g) {
  for (const name of Object.keys(g.attributes)) if (!["position", "normal"].includes(name)) g.deleteAttribute(name);
  return g;
}
function combine(items) {
  const values = items.map(g => tidy(g.index ? g.toNonIndexed() : g));
  const result = mergeGeometries(values, false);
  if (!result) throw new Error("Reference geometry merge failed");
  values.forEach(g => g.dispose());
  const indexed = mergeVertices(result, 1e-6); result.dispose(); return indexed;
}
function moved(g, x=0, y=0, z=0) { return g.translate(x,y,z); }
function box(x,y,z,w,h,d) {
  // Beveled edges carry genuine geometry, not a normal-map substitute.
  const s = new T.Shape(), r = Math.min(w,h,.02)/3;
  s.moveTo(-w/2+r,-h/2); s.lineTo(w/2-r,-h/2); s.quadraticCurveTo(w/2,-h/2,w/2,-h/2+r);
  s.lineTo(w/2,h/2-r); s.quadraticCurveTo(w/2,h/2,w/2-r,h/2);
  s.lineTo(-w/2+r,h/2); s.quadraticCurveTo(-w/2,h/2,-w/2,h/2-r);
  s.lineTo(-w/2,-h/2+r); s.quadraticCurveTo(-w/2,-h/2,-w/2+r,-h/2);
  const g = new T.ExtrudeGeometry(s,{depth:d,bevelEnabled:true,bevelSegments:2,steps:1,bevelSize:.002,bevelThickness:.002,curveSegments:3});
  return g.translate(x,y,z-d/2);
}
function revolve(profile, x=0, y=Y, z=0, segments=40) {
  const pts = profile.map(([axial,radius]) => new T.Vector2(radius,axial));
  return new T.LatheGeometry(pts,segments).rotateZ(-Math.PI/2).translate(x,y,z);
}
function ring(x,inner,outer,width,y=Y,z=0,segments=40) {
  return revolve([[-width/2,inner],[-width/2,outer-.002],[-width/2+.002,outer],
    [width/2-.002,outer],[width/2,outer-.002],[width/2,inner],[-width/2,inner]],x,y,z,segments);
}
function torus(x,radius,tube,y=Y,z=0) { return new T.TorusGeometry(radius,tube,8,48).rotateY(Math.PI/2).translate(x,y,z); }
function cylinder(x,radius,length,y=Y,z=0,segments=40) {
  return new T.CylinderGeometry(radius,radius,length,segments,1,false).rotateZ(Math.PI/2).translate(x,y,z);
}
function group(id,label,parent,offset) {
  components.push({id,label,parentId:parent,renderable:false,inventory:"assembly",note:"Selectable logical subassembly; inspect its separately modeled children."});
  const g = new T.Group(); g.name = label; g.userData.twin_component=id;
  (groups.get(parent)||scene).add(g); groups.set(id,g);
  motions.push({componentId:id,translation:offset,rotation:[0,0,0],pivot:[0,Y,0]});
}
function surfaceAudit(g) {
  const p=g.getAttribute("position"),index=g.index,edges=new Map();
  const key=i=>[p.getX(i),p.getY(i),p.getZ(i)].map(v=>Math.round(v*1e6)).join(",");
  const vertex=i=>key(index?index.getX(i):i);
  const count=index?index.count:p.count;
  for(let i=0;i<count;i+=3){
    const vertices=[vertex(i),vertex(i+1),vertex(i+2)];
    if(new Set(vertices).size<3)continue;
    for(let j=0;j<3;j++){
      const a=vertices[j],b=vertices[(j+1)%3],k=a<b?a+"|"+b:b+"|"+a;
      const entry=edges.get(k)||{count:0,winding:0};entry.count++;entry.winding+=a<b?1:-1;edges.set(k,entry);
    }
  }
  return {boundaryEdges:[...edges.values()].filter(e=>e.count===1).length,
    orientationErrors:[...edges.values()].filter(e=>e.winding!==0).length,
    nonManifoldEdges:[...edges.values()].filter(e=>e.count!==2).length};
}
function part(id,label,parent,geometry,mat,offset,{housing=false,combined="",rotation=[0,0,0]}={}) {
  let g=tidy(geometry); if (!g.index) g=mergeVertices(g,1e-6);
  // Smooth the cast/slotted stator envelope while retaining its sharp end faces.
  // Lathed/bearing/tube parts already carry authored smooth normals. Keeping those
  // attributes also avoids multiplying vertices along already smooth surfaces.
  if(id==="motor-stator"){
    const creased=toCreasedNormals(g,Math.PI/6),smoothed=mergeVertices(creased,1e-6);
    creased.dispose();g.dispose();g=smoothed;
  }
  if(id==="motor-rotor"){
    const positions=g.getAttribute("position"),normals=g.getAttribute("normal");
    for(let i=0;i<positions.count;i++){
      const y=positions.getY(i)-Y,z=positions.getZ(i),radius=Math.hypot(y,z);
      if(Math.abs(normals.getX(i))<.1&&radius>.125)normals.setXYZ(i,0,y/radius,z/radius);
    }
  }
  g.normalizeNormals();
  const normal=g.getAttribute("normal");
  for(let i=0;i<normal.count;i++)if(normal.getX(i)**2+normal.getY(i)**2+normal.getZ(i)**2<1e-12)normal.setXYZ(i,1,0,0);
  g.computeBoundingBox();
  const center=g.boundingBox.getCenter(new T.Vector3());
  g.translate(-center.x,-center.y,-center.z);
  const mesh=new T.Mesh(g,mat); mesh.position.copy(center);
  mesh.name=label; mesh.userData.twin_component=id;
  topology[id]=surfaceAudit(g);
  (groups.get(parent)||scene).add(mesh);
  components.push({id,label,parentId:parent,renderable:true,inventory:combined?"combined":"part",
    note:combined||"Individually selectable modeled part; illustrative reference designation.",
    material:mat.name,housing});
  motions.push({componentId:id,translation:offset,rotation,pivot:center.toArray()});
}
function bolt(x,y,z,axis="x") {
  const shaft=new T.CylinderGeometry(.008,.008,.065,12);
  const head=new T.CylinderGeometry(.017,.017,.013,6).translate(0,.035,0);
  const washer=new T.TorusGeometry(.013,.003,6,18).rotateX(Math.PI/2).translate(0,.026,0);
  const g=combine([shaft,head,washer]);
  if(axis==="x") g.rotateZ(-Math.PI/2);
  if(axis==="-x") g.rotateZ(Math.PI/2);
  return g.translate(x,y,z);
}
function bearing(prefix,label,parent,x,shift) {
  group(prefix,label,parent,shift);
  part(prefix+"-outer",label+" · outer race",prefix,
    revolve([[-.034,.082],[-.034,.105],[-.029,.11],[.029,.11],[.034,.105],
      [.034,.082],[.018,.082],[.009,.089],[-.009,.089],[-.018,.082],[-.034,.082]],x),
    materials.steel,[shift[0],shift[1]+.22,shift[2]]);
  part(prefix+"-inner",label+" · inner race",prefix,
    revolve([[-.034,.035],[-.034,.063],[-.018,.063],[-.009,.056],[.009,.056],
      [.018,.063],[.034,.063],[.034,.035],[-.034,.035]],x),
    materials.steel,[shift[0],shift[1]-.14,shift[2]]);
  const balls=[],cage=[];
  for(let i=0;i<9;i++){
    const a=i*Math.PI*2/9, cy=Y+.073*Math.cos(a), cz=.073*Math.sin(a);
    balls.push(new T.SphereGeometry(.016,16,8).translate(x,cy,cz));
    // Open pockets: two narrow cage rails joined by actual posts between balls.
    const b=a+Math.PI/9;
    cage.push(cylinder(x,.003,.039,Y+.073*Math.cos(b),.073*Math.sin(b),8));
  }
  part(prefix+"-balls",label+" · rolling-element set",prefix,combine(balls),materials.stainless,
    [shift[0],shift[1],shift[2]+.18],{combined:"Nine modeled balls intentionally combined as one selectable rolling-element set."});
  part(prefix+"-cage",label+" · open-pocket cage",prefix,
    combine([...cage,ring(x-.023,.068,.078,.004),ring(x+.023,.068,.078,.004)]),materials.brass,
    [shift[0],shift[1],shift[2]-.18],{combined:"Open cage rails and pocket bridges form one cage; the ball spaces are empty."});
}
group("pump","Pump assembly",null,[-.35,0,0]);
group("motor","Motor",null,[.4,0,0]);
group("coupling","Flexible coupling",null,[.1,0,0]);
part("base","Machined mounting base",null,
  booleanGeometry([box(.38,.055,0,3.2,.075,.8),box(.38,.12,-.20,3.0,.055,.18),box(.38,.12,.20,3.0,.055,.18)],[-.77,-.14,1.0,1.36].flatMap(x=>(x===-.14?[-.14,.14]:[-.20,.20]).map(z=>cylinder(0,.009,.3,0,0,16).rotateZ(Math.PI/2).translate(x,.10,z)))),
  materials.darkSteel,[0,-.12,0],{combined:"Base and two mounting rails with eight through mounting bores, combined as one part. Illustrative feet placement, not an installation drawing."});

// Volute: open central impeller chamber, a growing annular flow passage and a
// tangential discharge. These surfaces are illustrative, not validated CFD geometry.
function voluteWall(){
  const positions=[],normals=[],indices=[],steps=96,profiles=4;
  // Sweep the wall thickness, leaving the fluid passage genuinely empty.
  for(let i=0;i<=steps;i++){
    const a=i/steps*Math.PI*2, r=.285+.075*i/steps;
    for(const [xx,rr] of [[-.115,r],[-.115,r+.038],[.115,r+.038],[.115,r]]){
      positions.push(-.77+xx,Y+rr*Math.cos(a),rr*Math.sin(a));
    }
  }
  for(let i=0;i<steps;i++) for(let j=0;j<profiles;j++){
    const a=i*profiles+j,b=i*profiles+(j+1)%profiles,c=b+profiles,d=a+profiles;
    indices.push(a,b,d,b,c,d);
  }
  // Close the spiral tongue ends with real wall material, not the passage.
  indices.push(0,2,1,0,3,2,steps*4,steps*4+1,steps*4+2,steps*4,steps*4+2,steps*4+3);
  const g=new T.BufferGeometry();g.setAttribute("position",new T.Float32BufferAttribute(positions,3));g.setIndex(indices);g.computeVertexNormals();return g;
}
part("casing","Casing","pump",booleanGeometry([voluteWall(),ring(-.9,.102,.326,.035),ring(-.64,.042,.374,.035),
  box(-.77,.2765,-.20,.24,.25,.1),box(-.77,.2765,.20,.24,.25,.1)],
  [cylinder(0,.068,.7,0,0,40).rotateZ(Math.PI/2).translate(-.77,1.10,.27),...Array.from({length:8},(_,i)=>cylinder(-.9,.0105,.10,Y+.277*Math.cos(i*Math.PI/4),.277*Math.sin(i*Math.PI/4),16)),...[-.20,.20].map(z=>cylinder(0,.009,.4,0,0,16).rotateZ(Math.PI/2).translate(-.77,.27,z))]),materials.paint,[-.35,0,0],
  {housing:true,combined:"Boolean-unioned volute, rims and feet; open tangential discharge passage and eight cover bores. Illustrative passage proportions; no hydraulic validation."});
part("suction-cover","Suction cover and inlet flange","pump",
  booleanGeometry([revolve([[-.18,.098],[-.18,.16],[-.15,.16],[-.15,.115],[-.04,.115],[.0,.30],[.026,.30],[.026,.098],[-.18,.098]],-.949),
    ring(-1.129,.099,.17,.025)],
    [...Array.from({length:8},(_,i)=>cylinder(-.936,.0105,.07,Y+.277*Math.cos(i*Math.PI/4),.277*Math.sin(i*Math.PI/4),16)),
     ...Array.from({length:4},(_,i)=>cylinder(-1.129,.0105,.07,Y+.14*Math.cos(Math.PI/4+i*Math.PI/2),.14*Math.sin(Math.PI/4+i*Math.PI/2),16))]),materials.paint,[-.95,.12,0],{housing:true,rotation:[0,.12,0],combined:"Cast inlet cover and neck; the inlet bore is open."});
part("discharge","Tangential discharge neck and flange","pump",
  booleanGeometry([ring(0,.068,.088,.41,0,0,40).rotateZ(Math.PI/2).translate(-.77,1.035,.27),
    ring(0,.068,.135,.027,0,0,40).rotateZ(Math.PI/2).translate(-.77,1.24,.27)],
    Array.from({length:4},(_,i)=>cylinder(0,.01,.07,0,0,16).rotateZ(Math.PI/2).translate(-.77+.108*Math.cos(Math.PI/4+i*Math.PI/2),1.24,.27+.108*Math.sin(Math.PI/4+i*Math.PI/2)))),
  materials.paint,[-.35,.38,.12],{housing:true,combined:"Hollow discharge neck and flange; illustrative volute/neck junction."});
part("cover-gasket","Pump cover gasket","pump",booleanGeometry([ring(-.9205,.105,.306,.006)],Array.from({length:8},(_,i)=>cylinder(-.9205,.0105,.04,Y+.277*Math.cos(i*Math.PI/4),.277*Math.sin(i*Math.PI/4),16))),materials.rubber,[-.7,.08,0]);
part("impeller","Impeller","pump",(()=>{
  const items=[ring(-.79,.043,.254,.022),ring(-.855,.103,.245,.015),ring(-.803,.031,.065,.082)];
  for(let i=0;i<7;i++){
    const s=new T.Shape();
    s.moveTo(.07,0);s.bezierCurveTo(.12,-.01,.19,-.04,.245,-.08);
    s.lineTo(.25,-.067);s.bezierCurveTo(.20,-.027,.12,.005,.075,.012);s.closePath();
    const g=new T.ExtrudeGeometry(s,{depth:.055,bevelEnabled:true,bevelSize:.002,bevelThickness:.002,bevelSegments:2,curveSegments:14,steps:1});
    g.rotateY(Math.PI/2).rotateX(i*Math.PI*2/7).translate(-.846,Y,0);items.push(g);
  } return combine(items);
})(),materials.stainless,[-.68,.2,.05],{combined:"One cast reference impeller: two shrouds and seven curved, separately surfaced vanes with open passages."});
part("coupling-shaft","Coupling Shaft","pump",
  revolve([[-.85,0],[-.85,.031],[-.67,.031],[-.67,.035],[.10,.035],[.10,.028],[.30,.028],[.30,0],[-.85,0]],0),
  materials.steel,[-.15,.05,.38],{combined:"Stepped pump shaft; the coupling hubs and insert are separate parts."});
part("shaft-sleeve","Pump shaft sleeve","pump",ring(-.54,.0355,.048,.17),materials.stainless,[-.35,.12,.27]);
part("seal-seat","Mechanical seal · stationary ceramic seat","pump",ring(-.61,.049,.071,.025),materials.ceramic,[-.5,-.1,0]);
part("seal-face","Mechanical seal · rotating carbon face","pump",ring(-.57,.049,.07,.03),materials.carbon,[-.3,-.1,0]);
part("seal-o-ring","Mechanical seal · elastomer O-ring","pump",torus(-.625,.066,.004),materials.rubber,[-.6,-.12,.07]);
part("seal-spring","Mechanical seal · spring and retainer","pump",(()=>{
  const pts=[];for(let i=0;i<=240;i++){const a=i/240*Math.PI*12;pts.push(new T.Vector3(-.55+i/240*.07,Y+.055*Math.cos(a),.055*Math.sin(a)));}
  const curve=new T.CatmullRomCurve3(pts);return combine([new T.TubeGeometry(curve,240,.0025,5,false),ring(-.48,.045,.065,.008)]);
})(),materials.steel,[-.13,-.12,.12],{combined:"Helical spring and retainer, one selectable seal element. Spring end faces are open; this component does not receive section caps."});
part("bearing-frame","Pump bearing frame","pump",booleanGeometry([ring(-.14,.1102,.145,.52),
  box(-.14,.3365,-.10,.42,.37,.15),box(-.14,.3365,.10,.42,.37,.15)],[-.14,.14].map(z=>cylinder(0,.009,.5,0,0,16).rotateZ(Math.PI/2).translate(-.14,.33,z))),materials.paint,[-.28,-.1,0],
  {housing:true,combined:"Hollow bearing housing and mounting feet; races and rolling elements are separate."});
bearing("bearing","Bearing","pump",-.34,[-.24,.18,.24]);
bearing("pump-outboard-bearing","Outboard bearing","pump",.07,[.12,.18,-.24]);
part("bearing-cover","Bearing frame end cover","pump",ring(.13,.03,.14,.025),materials.paint,[.48,.05,0],{housing:true});
part("bearing-gasket","Bearing cover gasket","pump",ring(.114,.035,.13,.004),materials.rubber,[.33,.05,0]);
part("pump-spacer","Pump bearing spacer","pump",ring(-.12,.039,.052,.26),materials.steel,[-.1,-.05,-.25]);

part("coupling-pump-hub","Pump-side coupling hub","coupling",booleanGeometry([ring(.25,.028,.09,.105),...Array.from({length:3},(_,i)=>cylinder(.33,.012,.065,Y+.07*Math.cos(i*Math.PI*2/3),.07*Math.sin(i*Math.PI*2/3),16))]),materials.steel,[-.12,.13,0]);
part("coupling-spider","Elastomer coupling insert","coupling",(()=>{
  const parts=[ring(.345,.032,.048,.055)];
  for(let i=0;i<6;i++){const a=Math.PI/6+i*Math.PI/3;parts.push(box(0,.061,0,.055,.026,.025).rotateX(a).translate(.345,Y,0));}
  return combine(parts);
})(),materials.rubber,[.12,.28,0],{combined:"One molded insert with six real lobes; not a coupling stress model."});
part("coupling-motor-hub","Motor-side coupling hub","coupling",booleanGeometry([ring(.44,.028,.09,.105),...Array.from({length:3},(_,i)=>cylinder(.36,.012,.065,Y+.07*Math.cos(Math.PI/3+i*Math.PI*2/3),.07*Math.sin(Math.PI/3+i*Math.PI*2/3),16))]),materials.steel,[.33,.13,0]);
part("coupling-guard","Coupling guard","coupling",(()=>{
  const shape=new T.Shape();shape.absarc(0,0,.15,0,Math.PI,false);
  shape.lineTo(-.143,0);shape.absarc(0,0,.143,Math.PI,0,true);shape.closePath();
  return booleanGeometry([new T.ExtrudeGeometry(shape,{depth:.38,bevelEnabled:true,bevelSize:.001,bevelThickness:.001,bevelSegments:1,curveSegments:24}).rotateY(Math.PI/2).translate(.12,Y-.02,0),...[-.146,.146].map(z=>box(.31,.3965,z,.38,.49,.008))]);
})(),materials.motor,[.1,.65,.12],{housing:true,rotation:[.15,0,0]});

const MX=1.18;
part("motor-housing","Motor finned housing","motor",(()=>{
  const items=[ring(MX,.2332,.262,.78),box(MX,.2615,-.20,.56,.22,.13),box(MX,.2615,.20,.56,.22,.13)];
  for(let i=0;i<20;i++){const a=i*Math.PI*2/20;items.push(box(0,0,0,.65,.035,.008).rotateX(a).translate(MX,Y+.274*Math.cos(a),.274*Math.sin(a)));}
  return booleanGeometry(items,[1.0,1.36].flatMap(x=>[-.20,.20].map(z=>cylinder(0,.009,.4,0,0,16).rotateZ(Math.PI/2).translate(x,.27,z))));
})(),materials.motor,[.4,.12,.1],{housing:true,combined:"Hollow finned cast housing with mounting feet; no internal rotor/stator substitute."});
part("motor-stator","Stator laminated core","motor",(()=>{
  const outer=new T.Shape();outer.absarc(0,0,.233,0,Math.PI*2,false);
  // Slot centers are authored in the same Y/Z frame as the conductors below.
  const hole=new T.Path();for(let i=0;i<192;i++){const theta=-i/192*Math.PI*2;
    const off=Math.abs(Math.atan2(Math.sin(theta*12),Math.cos(theta*12)))/12;
    const r=off<=.10?.195:.128, u=-r*Math.sin(theta),v=r*Math.cos(theta);
    if(!i)hole.moveTo(u,v);else hole.lineTo(u,v);}
  hole.closePath();outer.holes.push(hole);
  return new T.ExtrudeGeometry(outer,{depth:.46,bevelEnabled:false,curveSegments:48,steps:1}).rotateY(Math.PI/2).translate(.95,Y,0);
})(),materials.darkSteel,[.4,.42,0],{combined:"One selectable slotted lamination-stack envelope. Individual sheet edges are visible on the separate rotor stack."});
for(let phase=0;phase<3;phase++){
  const coils=[];
  for(let slot=phase;slot<12;slot+=3)for(let turn=0;turn<2;turn++){
    const a=slot*Math.PI*2/12,b=a+Math.PI/2,r0=.150+turn*.011,r1=.177+turn*.011;
    const point=(x,theta,r)=>new T.Vector3(MX+x,Y+r*Math.cos(theta),r*Math.sin(theta));
    const pts=[];
    // Four axial legs fit each slot at distinct radial seats. End turns cross
    // between slots strictly outside the laminated stack's +/- .23 end faces.
    for(let k=0;k<9;k++)pts.push(point(-.245+k/8*.49,a,r0));
    for(let k=1;k<=24;k++){const t=k/24;pts.push(point(.245+(.035+phase*.011+turn*.008)*Math.sin(Math.PI*t),a+(b-a)*t,r0+(r1-r0)*t));}
    for(let k=1;k<=8;k++)pts.push(point(.245-k/8*.49,b,r1));
    for(let k=1;k<24;k++){const t=k/24;pts.push(point(-.245-(.035+phase*.011+turn*.008)*Math.sin(Math.PI*t),b+(a-b)*t,r1+(r0-r1)*t));}
    coils.push(new T.TubeGeometry(new T.CatmullRomCurve3(pts,true),56,.0035,8,true));
  }
  part("winding-"+String.fromCharCode(97+phase),"Copper winding phase "+String.fromCharCode(65+phase),"motor",combine(coils),materials.copper,
    [.4,.45*Math.cos(phase*Math.PI*2/3),.45*Math.sin(phase*Math.PI*2/3)],
    {combined:"Four closed coils with two modeled conductor bundles each, grouped by illustrative phase. Individual wire strands are intentionally combined; not an electrical winding specification."});
}
part("motor-rotor","Rotor lamination stack","motor",(()=>{
  const shape=new T.Shape();
  for(let i=0;i<48;i++){const a=i/48*Math.PI*2;
    if(!i)shape.moveTo(.126*Math.cos(a),.126*Math.sin(a));else shape.lineTo(.126*Math.cos(a),.126*Math.sin(a));}
  shape.closePath();
  const hole=(cx,cy,r,n)=>{const p=new T.Path();for(let i=0;i<n;i++){const a=-i/n*Math.PI*2;
    if(!i)p.moveTo(cx+r*Math.cos(a),cy+r*Math.sin(a));else p.lineTo(cx+r*Math.cos(a),cy+r*Math.sin(a));}p.closePath();return p;};
  shape.holes.push(hole(0,0,.035,24));
  for(let i=0;i<18;i++){const a=i*Math.PI*2/18;shape.holes.push(hole(.117*Math.cos(a),.117*Math.sin(a),.0064,8));}
  const pack=new T.ExtrudeGeometry(shape,{depth:.031,bevelEnabled:false,curveSegments:4,steps:1}).rotateY(Math.PI/2);
  const slices=[];for(let i=0;i<12;i++)slices.push(pack.clone().translate(MX-.20+i*.034,Y,0));pack.dispose();return combine(slices);
})(),materials.darkSteel,[.8,0,.22],{combined:"Twelve modeled slotted lamination packs share one selectable rotor-core identity. Individual thin sheets within each pack are intentionally combined. Actual cage-bar bores remain empty."});
part("rotor-cage","Rotor conductor cage","motor",(()=>{
  const bars=[ring(MX-.24,.112,.132,.016),ring(MX+.24,.112,.132,.016)];
  for(let i=0;i<18;i++){const a=i*Math.PI*2/18;bars.push(cylinder(MX,.0054,.48,Y+.117*Math.cos(a),.117*Math.sin(a),8));}return combine(bars);
})(),materials.copper,[.86,0,-.14],{combined:"Eighteen actual conductor bars and two end rings. Illustrative squirrel-cage geometry."});
part("motor-shaft","Motor rotor shaft","motor",revolve([[-.76,0],[-.76,.028],[-.38,.028],[-.38,.035],[.38,.035],[.38,.025],[.61,.025],[.61,0],[-.76,0]],MX),
  materials.steel,[1.15,0,0]);
bearing("motor-de-bearing","Motor drive-end bearing","motor",.84,[.22,-.2,.22]);
bearing("motor-nde-bearing","Motor non-drive-end bearing","motor",1.52,[.8,-.2,-.22]);
part("motor-front-cover","Motor drive-end cover","motor",booleanGeometry([ring(.765,.0355,.262,.05),ring(.84,.1102,.132,.11)]),materials.motor,[.08,.08,.1],{housing:true});
part("motor-back-cover","Motor non-drive-end cover","motor",booleanGeometry([ring(1.595,.0255,.262,.05),ring(1.52,.1102,.132,.11)],Array.from({length:4},(_,i)=>cylinder(1.595,.0105,.08,Y+.205*Math.cos(Math.PI/4+i*Math.PI/2),.205*Math.sin(Math.PI/4+i*Math.PI/2),16))),materials.motor,[1.1,.08,0],{housing:true,rotation:[0,.1,0]});
part("motor-fan","Motor cooling fan","motor",(()=>{
  const items=[ring(1.75,.026,.07,.035)];for(let i=0;i<10;i++){const a=i*Math.PI*2/10;
    items.push(box(0,.13,0,.022,.13,.04).rotateX(a).translate(1.75,Y,0));}return combine(items);
})(),materials.rubber,[1.35,.12,0],{combined:"Hub and ten real fan blades are one molded selectable component."});
part("fan-cover","Ventilated fan cover","motor",(()=>{
  const items=[ring(1.77,.215,.232,.23),ring(1.89,.201,.22,.009),ring(1.89,.12,.13,.009),ring(1.89,.025,.038,.009)];
  // Raised ribs are physical metal; annular regions between them are ventilation openings.
  for(let i=0;i<12;i++){const a=i*Math.PI*2/12;items.push(box(0,.12,0,.018,.18,.012).rotateX(a).translate(1.9,Y,0));}
  return combine(items);
})(),materials.motor,[1.6,.13,0],{housing:true,combined:"Open rib guard and annular rim. Not a sealed motor end wall."});
part("terminal-box","Motor terminal enclosure","motor",combine([
  box(MX-.12,Y+.33,0,.008,.12,.21),box(MX+.12,Y+.33,0,.008,.12,.21),
  box(MX,Y+.33,-.101,.25,.12,.008),box(MX,Y+.33,.101,.25,.12,.008),
  box(MX,Y+.273,0,.25,.008,.21),box(MX,Y+.4,0,.28,.012,.24)]),
  materials.motor,[.4,.8,0],{housing:true,combined:"Terminal enclosure and lid retained as one component. Electrical terminals are outside this mechanical reference's declared internal scope."});
for(let i=0;i<8;i++){
  const a=i*Math.PI/4;
  part("pump-cover-bolt-"+i,"Pump cover fastener "+(i+1),"pump",bolt(-.923,Y+.277*Math.cos(a),.277*Math.sin(a),"-x"),
    materials.steel,[-1.02,.12+.12*Math.cos(a),.12*Math.sin(a)],{combined:"Hex head, washer and shank. Cosmetic thread helices are intentionally omitted."});
}
for(let i=0;i<4;i++){
  const a=Math.PI/4+i*Math.PI/2;
  part("motor-tie-bolt-"+i,"Motor tie fastener "+(i+1),"motor",bolt(1.6,Y+.205*Math.cos(a),.205*Math.sin(a)),
    materials.steel,[1.28,.17*Math.cos(a),.17*Math.sin(a)],{combined:"Tie-bolt head, washer and shank; threads are intentionally combined/omitted from the viewing derivative."});
}
scene.updateMatrixWorld(true);
const closedSolids=components.filter(c=>c.renderable&&topology[c.id].boundaryEdges===0&&topology[c.id].orientationErrors===0&&topology[c.id].nonManifoldEdges===0).map(c=>c.id);
const inspector={
  version:"1.0.0",reference:"onesa-end-suction-pump-tefc-motor-v2.1",
  description:"Engineering-informed illustrative single-stage end-suction pump and TEFC squirrel-cage motor. No manufacturer identity, dimensions, certification or validated maintenance sequence.",
  motions,closedSolids,housingComponents:components.filter(c=>c.housing).map(c=>c.id),
  coverComponents:components.filter(c=>c.housing && /cover|guard|enclosure/.test(c.id)).map(c=>c.id),
  unavailable:[],
  scopeNotes:["Mechanical reference; terminal internals, cables and hydraulic CFD are outside the declared mechanical inspection scope.",
    "Thread helices and exact surface finishes are intentionally simplified; fastener assemblies remain modeled/selectable.",
    "Explosion is authored visualization, not an engineering-approved disassembly sequence.",
    "Hollow flow regions, shaft bores, cage pockets and winding gaps contain no modeled solid and must remain empty when sectioned.",
    "Open-ended seal spring does not receive cut caps."],
};
const exporter=new GLTFExporter();
const glb=await exporter.parseAsync(scene,{binary:true,onlyVisible:true,trs:true});
fs.writeFileSync(path.join(output,"pump.glb"),Buffer.from(glb));
fs.writeFileSync(path.join(output,"assembly.json"),JSON.stringify({components,inspection:inspector},null,2)+"\n");
fs.writeFileSync(path.join(output,"topology-audit.json"),JSON.stringify(topology,null,2)+"\n");
const data=JSON.parse(Buffer.from(glb).subarray(20,20+new DataView(glb).getUint32(12,true)).toString());
const triangles=data.meshes.reduce((n,m)=>n+m.primitives.reduce((s,p)=>s+data.accessors[p.indices??p.attributes.POSITION].count/3,0),0);
console.log(JSON.stringify({components:components.length,nodes:data.nodes.length,triangles,bytes:glb.byteLength,reference:inspector.reference}));
