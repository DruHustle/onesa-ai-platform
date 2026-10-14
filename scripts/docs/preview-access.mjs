// Keep the public Docs project test credential inside its verified Preview origin.
import fs from 'node:fs/promises';
import path from 'node:path';
const PROJECT='prj_Dtm2zO8sQQFqmnospPZgxbCi9Bbr';
const HEADER='x-vercel-protection-bypass';
export function previewAccess(credential,identity,origin,revision){
 const url=new URL(origin);
 if(!credential||typeof credential!=='object'||Array.isArray(credential)||!identity||typeof identity!=='object'||Array.isArray(identity)||!/^[a-f0-9]{40}$/.test(revision||'')||url.protocol!=='https:'||!url.hostname.endsWith('.vercel.app')||url.port||url.origin!==origin||identity.url!==origin||identity.projectId!==PROJECT||identity.state!=='READY'||!Object.hasOwn(identity,'target')||![null,'preview'].includes(identity.target)||identity.sourceRevision!==revision||!/^dpl_[a-zA-Z0-9]+$/.test(identity.deploymentId||'')||credential.projectId!==PROJECT||typeof credential.secret!=='string'||credential.secret.length<20||credential.secret.length>512||/[\r\n]/.test(credential.secret))throw new Error('PUBLIC_DOCS_PREVIEW_ACCESS_SCOPE');
 return boundPreviewTransport(credential.secret,origin);
}
export function boundPreviewTransport(secret,origin){
 return {
  async get(request,url){
   if(new URL(url).origin!==origin)throw new Error('PUBLIC_DOCS_PREVIEW_REQUEST_ORIGIN');
   try{return await request.get(url,{headers:{[HEADER]:secret},maxRedirects:0});}catch{throw new Error('PUBLIC_DOCS_PREVIEW_TRANSPORT_FAILED');}
  },
  async route(route){
   const headers={...route.request().headers()};delete headers[HEADER];
   if(new URL(route.request().url()).origin!==origin)return route.continue({headers});
   if(route.request().method()!=='GET')return route.abort();
   try{
    const response=await route.fetch({headers:{...headers,[HEADER]:secret},maxRedirects:0});
    return await route.fulfill({response});
   }catch{return route.abort();}
  },
 };
}
export async function installPreviewAccess(context,origin,revision,environment=process.env){
 const file=environment.ONESA_DOCS_PREVIEW_ACCESS_FILE;
 if(!file)return {get:(request,url)=>request.get(url,{maxRedirects:0})};
 const identityFile=environment.ONESA_DOCS_PREVIEW_IDENTITY_FILE;
 if(!identityFile||!revision)throw new Error('PUBLIC_DOCS_PREVIEW_IDENTITY_REQUIRED');
 for(const [privateFile,bound] of [[file,4096],[identityFile,64*1024]]){
  const stat=await fs.lstat(privateFile),parent=await fs.lstat(path.dirname(privateFile));
  if(!stat.isFile()||stat.isSymbolicLink()||(stat.mode&0o077)!==0||stat.size>bound||!parent.isDirectory()||parent.isSymbolicLink()||(parent.mode&0o022)!==0||await fs.realpath(path.dirname(privateFile))!==path.resolve(path.dirname(privateFile)))throw new Error('PUBLIC_DOCS_PREVIEW_PRIVATE_FILE');
 }
 if(path.dirname(file)!==path.dirname(identityFile))throw new Error('PUBLIC_DOCS_PREVIEW_PRIVATE_CUSTODY_SCOPE');
 let credential,identity;
 try{credential=JSON.parse(await fs.readFile(file,'utf8'));identity=JSON.parse(await fs.readFile(identityFile,'utf8'));}catch{throw new Error('PUBLIC_DOCS_PREVIEW_PRIVATE_INPUT_INVALID');}
 const access=previewAccess(credential,identity,origin,revision);
 await context.route('**/*',route=>access.route(route));
 return access;
}
