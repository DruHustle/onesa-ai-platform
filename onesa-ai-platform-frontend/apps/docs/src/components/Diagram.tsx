import React, {useEffect, useRef, useState} from 'react';
import Link from '@docusaurus/Link';
export type DiagramInfo = {id:string;title:string;view:string;status:string;source:string;url:string;nodes:{id:string;label:string;responsibility:string;url:string}[];relationships?:{from:string;to:string}[]};
export default function Diagram({diagram,onEntitySelect}:{diagram:DiagramInfo;onEntitySelect?:(name:string)=>void}) {
  const [svg,setSvg]=useState(''), [zoom,setZoom]=useState(1), [pan,setPan]=useState({x:0,y:0}), [selected,setSelected]=useState(''), [expanded,setExpanded]=useState(false);
  const drag=useRef<{x:number;y:number;px:number;py:number}|null>(null);
  useEffect(()=>{setZoom(1);setPan({x:0,y:0});setSelected('');fetch(`/generated/diagrams/${diagram.id}.svg`).then(r=>r.text()).then(setSvg);},[diagram.id]);
  useEffect(()=>{if(!expanded)return;const key=(e:KeyboardEvent)=>{if(e.key==='Escape')setExpanded(false);};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key);},[expanded]);
  const node=diagram.nodes.find(n=>n.id===selected);
  return <section className={expanded?'diagram-panel expanded':'diagram-panel'} aria-label={diagram.title}>
    <div className="diagram-toolbar"><strong>{diagram.title}</strong><button onClick={()=>setZoom(z=>Math.min(4,z+.25))} aria-label="Zoom in">＋</button><button onClick={()=>setZoom(z=>Math.max(.5,z-.25))} aria-label="Zoom out">−</button><button onClick={()=>{setZoom(1);setPan({x:0,y:0});}}>Reset</button><button onClick={()=>setExpanded(!expanded)}>{expanded?'Close enlarged view':'Enlarge diagram'}</button></div>
    <p className="evidence">{diagram.status}</p>
    <div className="diagram-canvas" onPointerDown={e=>{drag.current={x:e.clientX,y:e.clientY,px:pan.x,py:pan.y};e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={e=>{if(drag.current)setPan({x:drag.current.px+e.clientX-drag.current.x,y:drag.current.py+e.clientY-drag.current.y});}} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}} onClick={e=>{if(onEntitySelect)onEntitySelect((e.target as Element).textContent?.trim()||'');const group=(e.target as Element).closest('g.node');if(group){const found=diagram.nodes.find(n=>group.id.includes(`-${n.id}-`));if(found)setSelected(found.id);}}}>
      <div style={{transform:`translate(${pan.x}px,${pan.y}px) scale(${zoom})`,transformOrigin:'center'}} dangerouslySetInnerHTML={{__html:svg}} />
    </div>
    {!!diagram.nodes.length&&<label>Select a component <select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Choose a component</option>{diagram.nodes.map(n=><option key={n.id} value={n.id}>{n.label}</option>)}</select></label>}
    {node&&<aside className="component-detail"><h3>{node.label}</h3><p>{node.responsibility}</p><p>Relationships: {(diagram.relationships||[]).filter(r=>r.from===node.id||r.to===node.id).map(r=>`${r.from} → ${r.to}`).join('; ')||'See diagram arrows.'}</p><Link to={node.url}>Read component documentation →</Link> · <Link to="/api-explorer">Application API contracts</Link></aside>}
    <div className="asset-links"><Link to={diagram.url}>Technical reference</Link><a href={`/generated/diagrams/${diagram.id}.svg`} download>SVG</a><a href={`/generated/diagrams/${diagram.id}.png`} download>PNG</a><a href={`/generated/diagrams/${diagram.id}.mmd`} download>Editable Mermaid</a></div>
  </section>;
}
