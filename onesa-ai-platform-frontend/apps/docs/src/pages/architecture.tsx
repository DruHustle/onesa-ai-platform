import React,{useEffect,useState} from 'react';
import Layout from '@theme/Layout';
import Diagram,{type DiagramInfo} from '../components/Diagram';
export default function Architecture(){
 const [items,setItems]=useState<DiagramInfo[]>([]),[view,setView]=useState('logical'),[id,setId]=useState(''),[error,setError]=useState('');
 useEffect(()=>{const abort=new AbortController();fetch('/generated/diagrams.json',{signal:abort.signal}).then(r=>{if(!r.ok)throw new Error('Architecture catalog is unavailable.');return r.json();}).then((v:DiagramInfo[])=>{setItems(v);setView(v[0]?.view||'logical');setId(v[0]?.id||'');}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>abort.abort();},[]);
 const diagram=items.find(d=>d.id===id),views=Array.from(new Set(items.map(d=>d.view)));
 return <Layout title="Interactive architecture"><main className="portal-page"><div className="eyebrow">ONESA ECOSYSTEM / VISUAL REFERENCE</div><h1>Architecture, with evidence.</h1><p>Switch views, zoom or drag to pan, and select a component to inspect its role and relationships. Focus the diagram and use arrow keys to pan. Dashed paths identify optional or proposed work.</p>{error&&<p role="alert">{error}</p>}<div className="view-tabs" role="group" aria-label="Architecture view">{views.map(v=><button key={v} aria-pressed={view===v} onClick={()=>{setView(v);setId(items.find(d=>d.view===v)?.id||'');}}>{v==='logical'?'Logical architecture':v==='deployment'?'Deployment architecture':'Implemented schema'}</button>)}</div><label>Diagram <select aria-label="Diagram" value={id} onChange={e=>setId(e.target.value)}>{items.filter(d=>d.view===view).map(d=><option value={d.id} key={d.id}>{d.title}</option>)}</select></label>{diagram&&<Diagram diagram={diagram}/>}</main></Layout>;
}
