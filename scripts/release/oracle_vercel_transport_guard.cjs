// Pinned owner preload. The durable marker precedes the HTTP create attempt,
// including an SDK retry after a lost acknowledgement. No headers/body are logged.
const fs=require('node:fs'),path=require('node:path'),dc=require('node:diagnostics_channel');
const {syncBuiltinESMExports}=require('node:module');
const endpoint=/^\/v[0-9]+\/(?:now\/)?deployments(?:\?|$)/;
function createGuard(directory,approvedOrigin='https://api.vercel.com'){
 const scope=JSON.parse(fs.readFileSync(path.join(directory,'scope.json')));
 if(scope.request_budget!==1||!/^[a-f0-9-]{36}$/.test(scope.operation_id)||scope.repository!=='DruHustle/onesa-ai-platform'||scope.component!=='frontend'||!['staging','production'].includes(scope.environment))throw Error('Invalid owner transport scope');
 return function check(origin,method,requestPath){
  if(String(method).toUpperCase()!=='POST'||!endpoint.test(String(requestPath)))return;
  if(new URL(String(origin)).origin!==approvedOrigin)throw Error('Deployment create target refused');
  const name=path.join(directory,'create-request.json');let descriptor;
  try{descriptor=fs.openSync(name,'wx',0o600);}catch{throw Error('Deployment create already attempted; inspect only');}
  try{fs.writeFileSync(descriptor,JSON.stringify({...scope,method:'POST',origin:approvedOrigin,path:String(requestPath).split('?')[0],recorded_at:new Date().toISOString(),automatic_retry:false}));fs.fsyncSync(descriptor);}finally{fs.closeSync(descriptor);}
  const parent=fs.openSync(directory,'r');try{fs.fsyncSync(parent);}finally{fs.closeSync(parent);}
 };
}
function install(directory,approvedOrigin='https://api.vercel.com'){
 const check=createGuard(directory,approvedOrigin);
 const guarded=(origin,method,p)=>{try{check(origin,method,p);}catch{process.stderr.write('Oracle deployment transport refused a duplicate or foreign create; inspect retained operation.\n');process.exit(73);}};
 dc.subscribe('undici:request:create',({request})=>guarded(request.origin,request.method,request.path));
 for(const [name,protocol] of [['node:http','http:'],['node:https','https:']]){
  const module=require(name),original=module.request;
  module.request=function(...args){
   let url,options;
   if(typeof args[0]==='string'||args[0] instanceof URL){url=new URL(args[0]);options=args[1]&&typeof args[1]==='object'?args[1]:{};}
   else{options=args[0]||{};const host=options.hostname||options.host||'localhost';url=new URL((options.protocol||protocol)+'//'+host+(options.port?':'+options.port:'')+(options.path||'/'));}
   guarded(url.origin,options.method||'GET',options.path||url.pathname+url.search);
   return original.apply(this,args);
  };
 }
 syncBuiltinESMExports();
}
module.exports={createGuard,install};
if(process.env.ONESA_ORACLE_VERIFIER_PRELOAD==='1'){
 try{install('/private/transport');}catch{process.stderr.write('Oracle deployment transport custody unavailable; no create allowed.\n');process.exit(73);}
}
