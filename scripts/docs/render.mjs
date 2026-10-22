import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import sourceComments from './markdown-comments.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const app=path.join(root,'onesa-ai-platform-frontend/apps/docs');
const {version:documentationVersion}=JSON.parse(await fs.readFile(path.join(app,'package.json'),'utf8'));
const require=createRequire(path.join(app,'package.json'));
const {chromium}=require('@playwright/test');
const {build}=require('esbuild');
const MarkdownIt=require('markdown-it');
const rendererDependencies={'scripts/docs/markdown-comments.mjs':crypto.createHash('sha256').update(await fs.readFile(new URL('./markdown-comments.mjs',import.meta.url))).digest('hex')};
const cache=path.join(app,'.cache');await fs.mkdir(cache,{recursive:true});
await fs.writeFile(path.join(cache,'mermaid-entry.mjs'),`import mermaid from ${JSON.stringify(path.join(app,'node_modules/mermaid/dist/mermaid.esm.min.mjs'))}; window.mermaid=mermaid;`);
await build({entryPoints:[path.join(cache,'mermaid-entry.mjs')],bundle:true,format:'iife',outfile:path.join(cache,'mermaid.js'),logLevel:'silent'});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1400,height:1000},deviceScaleFactor:2});
await page.setContent('<html><body></body></html>');await page.addScriptTag({path:path.join(cache,'mermaid.js')});
await page.evaluate(()=>window.mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',themeVariables:{primaryColor:'#f5f7fa',primaryTextColor:'#10263e',primaryBorderColor:'#2366d1',lineColor:'#52789b',fontFamily:'Arial',fontSize:'15px'},flowchart:{htmlLabels:false,useMaxWidth:false},sequence:{useMaxWidth:false}}));
const render=async(source,id)=>page.evaluate(async({source,id})=>(await window.mermaid.render('diagram_'+id,source)).svg,{source,id});
const names=['technical-overview','system-architecture','software-design','api-reference','database-design','deployment-operations','model-serving','training-fine-tuning','security-data-protection','developer-getting-started','agent-framework','knowledge-rag'];
const titles=['Technical Overview','System Architecture','Software Design Specification','API Reference','Database Design','Deployment and Operations','AI Model Serving Architecture','Model Training and Fine-Tuning','Security and Data Protection','Developer Getting Started','Agent Framework','Knowledge and RAG Architecture'];
const books=[['product/PRD.md','product/USE_CASES.md','product/EUROPEAN_MARKET_RELEVANCE.md','product/ROADMAP.md'],['architecture/SYSTEM_ARCHITECTURE.md','architecture/COMPONENTS.md','adr/0001-platform-baseline.md','adr/0002-mvp-storage-and-runtime.md'],['design/BACKEND_DESIGN.md','design/FRONTEND_DESIGN.md','design/AGENT_DESIGN.md','design/MODEL_SERVING_DESIGN.md'],['api/API_REFERENCE.md','api/AUTHENTICATION.md','api/STREAMING.md'],['database/SCHEMA.md','database/MIGRATIONS.md','database/BACKUP_RESTORE.md'],['deployment/LOCAL_DEVELOPMENT.md','models/OLLAMA_SETUP.md','models/VLLM_DEPLOYMENT.md','operations/MONITORING.md','operations/RECOVERY.md','operations/INCIDENT_RESPONSE.md','database/BACKUP_RESTORE.md'],['models/LOCAL_INFERENCE.md','architecture/MODEL_SERVING.md','models/INFERENCE_BENCHMARKS.md','models/MODEL_EVALUATION.md'],['training/DATASET_STRATEGY.md','training/DATASET_FORMAT.md','training/FINE_TUNING.md','training/EVALUATION.md','training/MODEL_RELEASE.md'],['security/SECURITY_ARCHITECTURE.md','security/THREAT_MODEL.md','security/PRIVACY_AND_DATA_PROTECTION.md','security/SECRETS_MANAGEMENT.md'],['deployment/LOCAL_DEVELOPMENT.md','api/AUTHENTICATION.md','testing/TEST_STRATEGY.md'],['design/AGENT_DESIGN.md','api/API_REFERENCE.md'],['architecture/DATA_FLOWS.md','api/STREAMING.md','database/SCHEMA.md']];

const ecosystemBooks=[["complete-system-architecture", "Complete System Architecture", ["ecosystem/COMPLETE_ARCHITECTURE.md", "architecture/SYSTEM_ARCHITECTURE.md", "architecture/COMPONENTS.md", "ecosystem/INFRASTRUCTURE.md", "operations/TAILSCALE_ADMINISTRATION.md", "architecture/ONESA_DESIGN_SYSTEM.md"]], ["company-portal-design", "Company Portal Technical Design", ["ecosystem/PORTAL_DESIGN.md", "ecosystem/PORTAL_DATABASE.md", "ecosystem/PORTAL_ENGINEERING_DOCS_IDENTITY.md"]], ["ai-platform-design", "AI Platform Technical Design", ["architecture/SYSTEM_ARCHITECTURE.md", "design/BACKEND_DESIGN.md", "design/FRONTEND_DESIGN.md", "design/AGENT_DESIGN.md"]], ["robot-design", "AI Robot Technical Design", ["ecosystem/ROBOT_DESIGN.md", "ecosystem/ROBOT_DATABASE.md"]], ["ecosystem-api-reference", "Ecosystem API Reference", ["api/API_REFERENCE.md", "api/AUTHENTICATION.md", "api/STREAMING.md", "ecosystem/PORTAL_DESIGN.md", "ecosystem/ROBOT_DESIGN.md"]], ["ecosystem-database-design", "Ecosystem Database Design", ["database/SCHEMA.md", "database/MIGRATIONS.md", "ecosystem/PORTAL_DATABASE.md", "ecosystem/ROBOT_DATABASE.md"]], ["infrastructure-deployment", "Infrastructure and Deployment", ["ecosystem/INFRASTRUCTURE.md", "engineering/ORACLE_VM_OPERATIONS.md", "deployment/LOCAL_DEVELOPMENT.md", "ecosystem/PORTAL_DESIGN.md", "ecosystem/ROBOT_DESIGN.md"]], ["model-serving-training", "Model Serving and Training", ["models/LOCAL_INFERENCE.md", "architecture/MODEL_SERVING.md", "training/DATASET_STRATEGY.md", "training/DATASET_FORMAT.md", "training/FINE_TUNING.md", "training/EVALUATION.md", "training/MODEL_RELEASE.md"]], ["security-architecture", "Security Architecture", ["security/SECURITY_ARCHITECTURE.md", "security/THREAT_MODEL.md", "security/SECRETS_MANAGEMENT.md", "security/PRIVACY_AND_DATA_PROTECTION.md"]], ["operations-recovery", "Operations and Recovery", ["ecosystem/OPERATIONS.md", "operations/TAILSCALE_ADMINISTRATION.md", "operations/MONITORING.md", "operations/RECOVERY.md", "operations/INCIDENT_RESPONSE.md", "database/BACKUP_RESTORE.md"]]];
for(const [name,title,sources] of ecosystemBooks){names.push(name);titles.push(title);books.push(sources);}
const publicBooks={'technical-overview':['public/introduction.md','public/applications.md','public/architecture.md','public/roadmap.md'],'api-reference':['public/integration.md','public/authentication.md','public/streaming.md','public/examples.md'],'developer-getting-started':['public/quickstart.md','public/tutorials.md','public/troubleshooting.md'],'agent-framework':['public/applications.md','public/integration.md','public/examples.md'],'knowledge-rag':['public/applications.md','public/architecture.md','public/troubleshooting.md'],'security-data-protection':['public/privacy.md','public/authentication.md'],'model-serving':['public/models.md','public/roadmap.md']};
Object.assign(publicBooks,{"complete-system-architecture": ["public/ecosystem.md", "public/deployment-overview.md", "public/security-overview.md"], "company-portal-design": ["public/company-portal.md", "public/security-overview.md", "public/deployment-overview.md"], "ai-platform-design": ["public/ai-platform.md", "public/architecture.md", "public/models.md", "public/authentication.md"], "robot-design": ["public/robot.md", "public/security-overview.md", "public/deployment-overview.md"]});
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const css=`@page{size:A4;margin:21mm 16mm 20mm}*{box-sizing:border-box}body{font-family:Arial,sans-serif;color:#10263e;font-size:10pt;line-height:1.55}h1,h2,h3{line-height:1.22;break-after:avoid}h1{font-size:24pt;letter-spacing:-.7pt}h2{font-size:17pt;margin:20pt 0 10pt}h3{font-size:12pt}a{color:#2366d1;text-decoration:none}p,li{orphans:3;widows:3}table{border-collapse:collapse;width:100%;table-layout:fixed;margin:12pt 0;font-size:8pt}td,th{border:1px solid #bfcfc6;padding:5pt;overflow-wrap:anywhere;vertical-align:top}th{background:#edf3fa;text-align:left}thead{display:table-header-group}tr{break-inside:avoid}pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;background:#edf3fa;border-left:3pt solid #2366d1;padding:10pt;font-size:8pt;line-height:1.45}code{font-family:monospace;font-size:8pt;overflow-wrap:anywhere}.cover{break-after:page;min-height:220mm;display:flex;flex-direction:column;justify-content:center;border-top:8pt solid #2366d1}.cover h1{font-size:35pt;max-width:155mm}.brand{font-weight:bold;font-size:19pt}.eyebrow{font-size:9pt;text-transform:uppercase;letter-spacing:2pt;color:#2366d1}.toc{break-after:page}.section{margin-top:18pt}.figure{break-inside:avoid;margin:14pt 0}.figure svg{width:100%;height:auto;max-height:190mm}.caption{font-size:8pt;color:#52789b}img{max-width:100%;max-height:160mm;object-fit:contain}blockquote{border-left:2pt solid #a8c1b3;padding-left:10pt}ul{padding-left:18pt}.refs{font-size:9pt}.status{padding:10pt;background:#edf3fa}`;
let counter=0;
for(const scope of ['public','internal']){
 const staticDir=path.join(app,'.generated',scope,'static/generated');
 const catalog=JSON.parse(await fs.readFile(path.join(staticDir,'diagrams.json'),'utf8'));
 const sourceProvenance=JSON.parse(await fs.readFile(path.join(staticDir,'provenance.json'),'utf8'));
 const internalSourceTexts=scope==='internal'?JSON.parse(await fs.readFile(path.join(cache,'authoritative/source-texts-internal.json'),'utf8')):null;
 const sourceText=async doc=>{
  const raw=scope==='public'?await fs.readFile(path.join(root,'docs',doc),'utf8'):internalSourceTexts[doc];
  if(typeof raw!=='string'||crypto.createHash('sha256').update(raw).digest('hex')!==sourceProvenance.sources['docs/'+doc])throw new Error('Classified manual source differs from its actual provenance');
  return raw;
 };

 const diagramDir=path.join(staticDir,'diagrams');await fs.rm(diagramDir,{recursive:true,force:true});await fs.mkdir(diagramDir,{recursive:true});
 const svgById={};
 for(const diagram of catalog){
  const source=await fs.readFile(path.join(root,diagram.source),'utf8');
  const svg=await render(source,scope+'_'+diagram.id.replaceAll('-','_'));svgById[diagram.id]=svg;
  await fs.writeFile(path.join(diagramDir,diagram.id+'.svg'),svg);await fs.writeFile(path.join(diagramDir,diagram.id+'.mmd'),source);
  const shot=await browser.newPage({viewport:{width:1400,height:1800},deviceScaleFactor:2});await shot.setContent(`<html><body style="margin:0;background:white"><div style="padding:24px">${svg}</div></body></html>`);await shot.locator('svg').evaluate(el=>{el.style.maxWidth='1350px';el.style.width='100%';el.style.height='auto';});await shot.locator('svg').screenshot({path:path.join(diagramDir,diagram.id+'.png')});
  const figure=await browser.newPage();await figure.setContent(`<html lang="en"><head><title>${escape(diagram.title)}</title><style>@page{size:A4;margin:15mm}body{font:12px Arial;color:#10263e}svg{max-width:100%;max-height:220mm;height:auto}h1{font-size:20px}p{overflow-wrap:anywhere}</style></head><body><h1>${escape(diagram.title)}</h1><p>${escape(diagram.status)}</p>${svg}<p>${escape(diagram.explanation||diagram.status)}</p><p>${escape(scope)} · v${documentationVersion} · source ${escape(diagram.source)} · revision ${escape(diagram.revision||'')}</p></body></html>`);
  await figure.pdf({path:path.join(diagramDir,diagram.id+'.pdf'),format:'A4',printBackground:true,tagged:true});await figure.close();await shot.close();
 }
 const policy=JSON.parse(await fs.readFile(path.join(root,'docs/documentation-policy.json'),'utf8'));
 const selectedNames=scope==='public'?policy.public_pdfs:names;
 const manuals=[];const manualDir=path.join(staticDir,'manuals');await fs.rm(manualDir,{recursive:true,force:true});await fs.mkdir(manualDir,{recursive:true});
 for(const name of selectedNames){
  const index=names.indexOf(name), title='Onesa — '+titles[index];
  const documents=scope==='public'?publicBooks[name]:books[index];
  const md=new MarkdownIt({html:false,linkify:true}).use(sourceComments);
  // Embed only classified, allowlisted local screenshots. PDF rendering never fetches
  // remote images or resolves arbitrary Markdown file paths.
  const screenshotUrls=JSON.parse(await fs.readFile(path.join(staticDir,'screenshots.json'),'utf8'));
  const screenshotData={};
  for(const [id,url] of Object.entries(screenshotUrls)){
   if(!policy.public_screenshots.includes(id)||url!==`/generated/screenshots/${id}.png`)throw new Error('Unapproved screenshot source');
   const file=path.join(staticDir,'screenshots',id+'.png');const stat=await fs.lstat(file);
   if(!stat.isFile()||stat.isSymbolicLink())throw new Error('Screenshot must be a regular classified artifact');
   const bytes=await fs.readFile(file);if(bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a')throw new Error('Invalid PNG screenshot');
   screenshotData[url]='data:image/png;base64,'+bytes.toString('base64');
  }
  const defaultImage=md.renderer.rules.image;
  md.renderer.rules.image=(tokens,i,opts,env,self)=>{
   const token=tokens[i],url=token.attrGet('src');
   if(!screenshotData[url])throw new Error('Document image is not an available classified screenshot');
   token.attrSet('src',screenshotData[url]);return defaultImage(tokens,i,opts,env,self);
  };
  const toc=[];let section=0;
  md.renderer.rules.heading_open=(tokens,i)=>{const level=Number(tokens[i].tag.slice(1)),text=tokens[i+1].content,id=`section-${++section}`;if(level<=2)toc.push({id,text,level});return `<${tokens[i].tag} id="${id}"><span>${section}. </span>`;};
  const defaultFence=md.renderer.rules.fence;
  md.renderer.rules.fence=(tokens,i,opts,env,self)=>tokens[i].info.trim()==='mermaid'?'<p class="caption">Editable source diagram; see the rendered architecture figures and portal.</p>':defaultFence(tokens,i,opts,env,self);
  let currentDoc='';
  const base=scope==='public'?'https://docs.onesa.eu':process.env.ONESA_INTERNAL_DOCUMENTATION_URL||'https://docs.engineering.onesa.eu';
  const defaultLink=md.renderer.rules.link_open||((tokens,i,opts,env,self)=>self.renderToken(tokens,i,opts));
  md.renderer.rules.link_open=(tokens,i,opts,env,self)=>{
   const token=tokens[i], target=token.attrGet('href')||'';
   if(target.startsWith('/')) token.attrSet('href',base+target);
   else if(!/^(?:https?:|mailto:|#)/.test(target)){
    const [file,anchor]=target.split('#'); const resolved=path.resolve(root,'docs',path.dirname(currentDoc),file);
    const relative=path.relative(path.join(root,'docs'),resolved).replaceAll(path.sep,'/');
    if(relative.endsWith('.md')&&!relative.startsWith('../'))token.attrSet('href',base+'/docs/'+relative.replace(/\.md$/,'')+(anchor?'#'+anchor:''));
   }
   return defaultLink(tokens,i,opts,env,self);
  };
  let body='';
  for(const doc of documents){currentDoc=doc;const raw=await sourceText(doc);body+=`<section class="section">${md.render(raw)}<p class="refs">Source: <a href="${base}/docs/${doc.replace(/\.md$/,'')}">${escape(doc)}</a></p></section>`;}
  if(name==='api-reference'||name==='ecosystem-api-reference'){
   const schemas=await Promise.all(['openapi.json',...(name==='ecosystem-api-reference'?['openapi-portal.json','openapi-robot.json']:[])].map(async file=>[file,JSON.parse(await fs.readFile(path.join(staticDir,file),'utf8'))]));
   for(const [contract,schema] of schemas){
   body+=`<h1>${escape(contract.replace('.json',''))} — source-generated contract</h1>`;
   body+='<section class="section"><h1>Generated endpoint contracts</h1><p>Exact request/response schemas follow. Common runtime errors and SSE behavior are described in the sourced reference.</p>';
   const describe=s=>!s?'unspecified':s.$ref?s.$ref.split('/').pop():s.enum?'enum '+s.enum.join(', '):s.anyOf?s.anyOf.map(describe).join(' | '):s.oneOf?s.oneOf.map(describe).join(' | '):s.type==='array'?'array of '+describe(s.items):s.type||'object';
   const fields=s=>s?.properties?'<table><thead><tr><th>Field</th><th>Type</th><th>Required / constraints</th></tr></thead><tbody>'+Object.entries(s.properties).map(([key,value])=>`<tr><td>${escape(key)}</td><td>${escape(describe(value))}</td><td>${escape([(s.required||[]).includes(key)?'required':'optional',...Object.entries(value).filter(([k])=>['minimum','maximum','minLength','maxLength','pattern','format'].includes(k)).map(([k,v])=>k+': '+v)].join('; '))}</td></tr>`).join('')+'</tbody></table>':'<p>Schema: '+escape(describe(s))+'</p>';
   body+=`<p>Full machine-readable contract: <a href="${base}/generated/${contract}">${escape(contract)}</a>. Explorers preserve the complete contract; this appendix summarizes the generated fields.</p>`;
   for(const [url,operations] of Object.entries(schema.paths))for(const [method,operation] of Object.entries(operations)){
    if(!['get','post','patch','delete','put'].includes(method))continue;
    body+=`<h2>${escape(method.toUpperCase()+' '+url)}</h2><p>${escape(operation.summary||'')}</p><p>Authentication: ${escape(JSON.stringify(operation.security??schema.security??'see product authentication requirements'))}.</p>`;
    if(operation.parameters?.length)body+='<ul>'+operation.parameters.map(p=>`<li>${escape(p.in+' '+p.name+' — '+describe(p.schema)+(p.required?' required':''))}</li>`).join('')+'</ul>';
    for(const [type,content] of Object.entries(operation.requestBody?.content||{}))body+=`<h3>Request ${escape(type)}</h3>`+fields(content.schema);
    body+='<h3>Responses</h3><ul>'+Object.entries(operation.responses||{}).map(([status,response])=>`<li>${escape(status+' — '+(response.description||'')+' '+Object.entries(response.content||{}).map(([mime,c])=>mime+': '+describe(c.schema)).join('; '))}</li>`).join('')+'</ul>';
   }
   body+='<h1>Generated JSON schemas</h1>';for(const [name,s] of Object.entries(schema.components?.schemas||{}))body+=`<h2>${escape(name)}</h2>`+fields(s);body+='</section>';
   }
  }
  const ecosystemFigures={'complete-system-architecture':['public-ecosystem','public-portal','public-ai-platform','public-robot'],'company-portal-design':['public-portal','portal-database-identity','portal-database-content','portal-database-business','portal-database-documents','portal-database-operations'],'ai-platform-design':['public-ai-platform','public-routing','public-rag','public-agents','public-travel'],'robot-design':['public-robot','public-ros2','public-safety','robot-database'],'ecosystem-api-reference':['public-auth'],'ecosystem-database-design':['database-auth','database-chat','database-knowledge','portal-database-identity','portal-database-content','portal-database-business','portal-database-documents','portal-database-operations','robot-database'],'infrastructure-deployment':['public-deployment','public-model-host','public-release'],'model-serving-training':['inference','lifecycle','registry'],'security-architecture':['authentication','public-auth','public-safety'],'operations-recovery':['public-recovery','monitoring']};
  const diagramIds=scope==='internal'&&name==='company-portal-design'?['portal-database','portal-database-identity','portal-database-content','portal-database-business','portal-database-documents','portal-database-operations','portal-database-governance','portal-database-lifecycle','portal-database-access','engineering-docs-identity']:scope==='internal'&&name==='infrastructure-deployment'?['infrastructure-current']:ecosystemFigures[name]||(scope==='public'?['public-system',...(name==='knowledge-rag'?['public-rag']:name==='agent-framework'?['public-agent']:['public-inference'])]:name==='database-design'?['database-auth','database-chat','database-knowledge','database-agents','database-travel','registry']:name==='deployment-operations'?['apple-silicon','compose','nvidia','distributed']:name==='training-fine-tuning'?['lifecycle','registry']:name==='agent-framework'?['agents']:name==='knowledge-rag'?['rag']:name==='model-serving'?['inference','apple-silicon']:name==='security-data-protection'?['authentication']:['system','components']);
  let figures='<section class="section"><h1>Architecture illustrations</h1>';
  for(const id of diagramIds){if(!svgById[id])continue;const d=catalog.find(d=>d.id===id);figures+=`<figure class="figure">${svgById[id]}<figcaption class="caption">${escape(d.title)} · ${escape(d.status)}</figcaption></figure>`;}figures+='</section>';
  const now=process.env.SOURCE_DATE_EPOCH?new Date(Number(process.env.SOURCE_DATE_EPOCH)*1000):new Date();const date=now.toISOString().slice(0,10);
  const html=`<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${escape(title)}</title><style>${css}</style></head><body><section class="cover"><p class="brand">Onesa</p><p class="eyebrow">${scope} documentation / ${documentationVersion}</p><h1>${escape(titles[index])}</h1><p>AI software. Applications. Robotics.</p><p class="status">Version ${documentationVersion} · Generated ${date}<br>Classification: ${scope}<br>Status: Development reference; verified, mock, unverified and proposed work labelled.</p></section><section class="toc"><h1>Contents</h1><ol>${toc.map(t=>`<li><a href="#${t.id}">${escape(t.text)}</a></li>`).join('')}<li>Generated contracts / architecture illustrations where applicable</li></ol></section>${figures}${body}</body></html>`;
  const pdfPage=await browser.newPage();await pdfPage.setContent(html,{waitUntil:'load'});await pdfPage.emulateMedia({media:'print'});
  const file=`${String(index+1).padStart(2,'0')} — ${title}.pdf`;
  await pdfPage.pdf({path:path.join(manualDir,file),format:'A4',printBackground:true,displayHeaderFooter:true,tagged:true,outline:true,headerTemplate:`<div style="font:8px Arial;width:100%;padding:0 16mm;color:#2366d1">${escape(title)} · ${scope.toUpperCase()} · v${documentationVersion}</div>`,footerTemplate:'<div style="font:8px Arial;width:100%;padding:0 16mm;color:#52789b">Onesa · Engineering reference <span style="float:right"><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',margin:{top:'21mm',right:'16mm',bottom:'20mm',left:'16mm'}});await pdfPage.close();
  const bytes=await fs.readFile(path.join(manualDir,file));manuals.push({name:title,file,category:name,classification:scope,description:titles[index]+' derived from classified source records',version:documentationVersion,date,status:'Development reference',sha256:crypto.createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length,pages:0,source_hashes:Object.fromEntries(await Promise.all(documents.map(async doc=>["docs/"+doc,crypto.createHash("sha256").update(await sourceText(doc)).digest("hex")]))),protected_source_bundle_sha256:scope==='internal'?sourceProvenance.protected_document_sources?.bundle_sha256??null:null,renderer_sha256:crypto.createHash("sha256").update(await fs.readFile(fileURLToPath(import.meta.url))).digest("hex"),renderer_dependencies:rendererDependencies});counter++;
 }
 await fs.writeFile(path.join(staticDir,'manuals.json'),JSON.stringify(manuals,null,2)+'\n');
 const output=path.join(root,'docs/generated',scope);await fs.mkdir(output,{recursive:true,mode:scope==='internal'?0o700:0o755});if(scope==='internal')await fs.chmod(output,0o700);await fs.rm(path.join(output,'diagrams'),{recursive:true,force:true});await fs.rm(path.join(output,'manuals'),{recursive:true,force:true});await fs.cp(diagramDir,path.join(output,'diagrams'),{recursive:true});await fs.cp(manualDir,path.join(output,'manuals'),{recursive:true});await fs.copyFile(path.join(staticDir,'manuals.json'),path.join(output,'manuals.json'));
 console.log(`${scope}: ${catalog.length} SVG/PNG/PDF diagrams, ${manuals.length} real PDF manuals`);
}
await browser.close();console.log(`Rendered ${counter} classified manuals.`);
