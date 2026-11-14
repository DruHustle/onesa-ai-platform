import React,{useEffect,useState} from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Diagram,{type DiagramInfo} from '../components/Diagram';
import {useEngineeringNavigation} from '../components/EngineeringNavigation';
export default function Architecture(){
 const {siteConfig}=useDocusaurusContext();const internal=siteConfig.customFields?.scope==='internal';
 const {navigation,error:navigationError}=useEngineeringNavigation(internal);
 const [items,setItems]=useState<DiagramInfo[]>([]),[view,setView]=useState('logical'),[id,setId]=useState(''),[error,setError]=useState('');
 useEffect(()=>{const abort=new AbortController();fetch('/generated/diagrams.json',{signal:abort.signal}).then(r=>{if(!r.ok)throw new Error('Architecture catalog is unavailable.');return r.json();}).then((v:DiagramInfo[])=>{const requested=new URLSearchParams(window.location.search).get('diagram');const first=v.find(d=>d.id===requested)||(internal?v.find(d=>d.id==='ecosystem-current'):undefined)||v[0];setItems(v);setView(first?.view||'logical');setId(first?.id||'');}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>abort.abort();},[internal]);
 const diagram=items.find(d=>d.id===id),views=Array.from(new Set(items.map(d=>d.view)));
 function select(next:string){const found=items.find(d=>d.id===next);if(found){setView(found.view);setId(next);window.history.replaceState(null,'',`?diagram=${encodeURIComponent(next)}`);}}
 return <Layout title="Architecture & Workflows"><main className="portal-page"><div className="eyebrow">ONESA ECOSYSTEM / {internal?'INTERNAL':'PUBLIC'} VISUAL REFERENCE</div><h1>Architecture &amp; Workflows</h1><p>Switch views, zoom or drag to pan, and select a component to inspect its role and relationships. Focus the diagram and use arrow keys to pan. Dashed paths identify optional or proposed work. Status labels distinguish implemented software, verified staging and production qualification.</p>{(error||navigationError)&&<p role="alert">{error||navigationError}</p>}
 {navigation&&<><nav className="workflow-index" aria-label="Architecture & Workflows sections">{navigation.architecture.map(topic=><button key={topic.id} onClick={()=>select(topic.diagram)} aria-pressed={id===topic.diagram}>{topic.title}</button>)}</nav><p><Link to="/onboarding">Start Here — Onesa Engineering</Link> · <Link to="/docs/ecosystem/VISUAL_WORKFLOWS">Editable diagram index and evidence</Link> · <Link to="/database">Generated database relationships</Link></p></>}
 <div className="view-tabs" role="group" aria-label="Architecture view">{views.map(v=><button key={v} aria-pressed={view===v} onClick={()=>{setView(v);setId(items.find(d=>d.view===v)?.id||'');}}>{v==='logical'?'Logical architecture':v==='deployment'?'Deployment architecture':'Implemented schema'}</button>)}</div><label>Diagram <select aria-label="Diagram" value={id} onChange={e=>select(e.target.value)}>{items.filter(d=>d.view===view).map(d=><option value={d.id} key={d.id}>{d.title}</option>)}</select></label>{diagram&&<Diagram diagram={diagram}/>}
 {navigation&&<section><h2>Detailed architecture references</h2><div className="topic-grid">{navigation.architecture.map(topic=><Link className="topic-card" key={topic.id} to={topic.url}><h3>{topic.title}</h3><p>{topic.summary}</p><strong>Read reference →</strong></Link>)}</div></section>}
 </main></Layout>;
}
