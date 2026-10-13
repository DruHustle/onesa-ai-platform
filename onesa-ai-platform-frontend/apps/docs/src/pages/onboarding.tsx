import React,{useEffect,useState} from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useBrokenLinks from '@docusaurus/useBrokenLinks';
import Diagram,{type DiagramInfo} from '../components/Diagram';
import {useEngineeringNavigation} from '../components/EngineeringNavigation';

export default function Onboarding(){
  const brokenLinks=useBrokenLinks();
  ['1','2','3','4'].forEach(id=>brokenLinks.collectAnchor(`day-${id}`));
  const {navigation,error}=useEngineeringNavigation(true);
  const [diagrams,setDiagrams]=useState<DiagramInfo[]>([]),[completed,setCompleted]=useState<string[]>([]),[assetError,setAssetError]=useState('');
  useEffect(()=>{
    try{const saved=JSON.parse(localStorage.getItem('onesa-engineering-learning-v1')||'[]');if(Array.isArray(saved)&&saved.every(x=>typeof x==='string'))setCompleted(saved);}catch{/* Browser notes are optional. */}
    const abort=new AbortController();
    fetch('/generated/diagrams.json',{signal:abort.signal}).then(r=>{if(!r.ok)throw new Error('Onboarding diagrams are unavailable.');return r.json();}).then(setDiagrams).catch(e=>{if(e.name!=='AbortError')setAssetError(e.message);});
    return()=>abort.abort();
  },[]);
  function toggle(id:string){const next=completed.includes(id)?completed.filter(x=>x!==id):[...completed,id];setCompleted(next);try{localStorage.setItem('onesa-engineering-learning-v1',JSON.stringify(next));}catch{/* Learning remains usable without storage. */}}
  return <Layout title="Start Here — Onesa Engineering" description="Four-day visual learning path for the Onesa ecosystem"><main className="portal-page">
    <div className="eyebrow">INTERNAL ENGINEERING / LEARNING PATH</div><h1>Start Here — Onesa Engineering</h1>
    <p>Understand the products, follow the software, learn delivery and practice operations. Checkpoints are browser-local learning notes; they grant no access and do not qualify a release.</p>
    {(error||assetError)&&<p role="alert">{error||assetError}</p>}
    <nav className="learning-days" aria-label="Four-day learning path">{navigation?.days.map(day=><a key={day.id} href={`#day-${day.id}`}>{day.title}</a>)}</nav>
    <div className="hero-actions"><Link className="button button--primary" to="/architecture">Architecture &amp; Workflows</Link><Link className="button button--secondary" to="/docs/onboarding/FIRST_CONTRIBUTION">First Engineering Contribution</Link></div>
    {!navigation&&['1','2','3','4'].map(id=><section className="learning-stage" id={`day-${id}`} key={id} aria-busy="true"><h2>Day {id}</h2><p>Loading the learning workflow…</p></section>)}
    {navigation?.days.map(day=>{const diagram=diagrams.find(d=>d.id===day.diagram);return <section className="learning-stage" id={`day-${day.id}`} key={day.id} aria-labelledby={`day-title-${day.id}`}>
      <h2 id={`day-title-${day.id}`}>{day.title}</h2><h3>Learning objectives</h3><ul>{day.objectives.map(objective=><li key={objective}>{objective}</li>)}</ul>
      {diagram&&<Diagram diagram={diagram}/>}<h3>Practical checkpoints</h3>
      <div className="learning-checkpoints">{day.checkpoints.map((checkpoint,i)=>{const id=`${day.id}:${i}`;return <label key={id}><input type="checkbox" checked={completed.includes(id)} onChange={()=>toggle(id)}/> <span>{checkpoint}</span></label>;})}</div>
      <p aria-live="polite">{day.checkpoints.filter((_,i)=>completed.includes(`${day.id}:${i}`)).length} of {day.checkpoints.length} learning checkpoints completed.</p>
      <ul>{day.references.map(ref=><li key={ref.url}><Link to={ref.url}>{ref.title}</Link></li>)}</ul><Link to={day.url}>Commands, source references and completion checklist →</Link>
    </section>;})}
    <h2>Engineering Onboarding reference</h2><nav className="topic-grid" aria-label="Engineering Onboarding chapters">{navigation?.chapters.map((chapter,i)=><Link className="topic-card" key={chapter.title} to={chapter.url}><span>{String(i+1).padStart(2,'0')}</span><h3>{chapter.title}</h3><strong>Read reference →</strong></Link>)}</nav>
    {navigation&&<p className="source-note">Reviewed {navigation.reviewed_at} · documentation v{navigation.version}. Exact build revision is available in generated provenance. <Link to="/docs/ecosystem/VISUAL_WORKFLOWS">Diagram index and evidence limits</Link>.</p>}
  </main></Layout>;
}
