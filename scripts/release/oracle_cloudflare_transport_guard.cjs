// The commissioned publisher installs this before the pinned Wrangler CLI.
// One durable dispatch budget belongs to an operation, across processes/restarts.
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {createHash}=require('node:crypto');

function privateFile(file,maximum){
 if(!path.isAbsolute(file))throw Error('ABSOLUTE_PRIVATE_GUARD_FILE_REQUIRED');
 const stat=fs.lstatSync(file);
 if(!stat.isFile()||stat.isSymbolicLink()||(stat.mode&0o077)||stat.size>maximum)throw Error('PRIVATE_GUARD_FILE_CUSTODY_REQUIRED');
 return fs.readFileSync(file);
}
function durable(file,value){
 const fd=fs.openSync(file,fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
 try{fs.writeFileSync(fd,JSON.stringify(value));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
 const directory=fs.openSync(path.dirname(file),fs.constants.O_RDONLY);try{fs.fsyncSync(directory);}finally{fs.closeSync(directory);}
}
function configuration(file,pin){
 if(!/^[a-f0-9]{64}$/.test(pin))throw Error('LITERAL_GUARD_CONFIG_PIN_REQUIRED');
 const raw=privateFile(file,32768);if(createHash('sha256').update(raw).digest('hex')!==pin)throw Error('GUARD_CONFIG_CHANGED');
 const value=JSON.parse(raw);
 const keys=['schema_version','account_id','project','operation_id','source_commit','artifact_manifest_sha256','environment','create_intent'];
 if(Object.keys(value).sort().join()!==keys.sort().join()||value.schema_version!==1||!/^[a-f0-9]{32}$/.test(value.account_id)||value.project!=='onesa-engineering-docs'||!/^[a-f0-9-]{36}$/.test(value.operation_id)||!/^[a-f0-9]{40}$/.test(value.source_commit)||!/^[a-f0-9]{64}$/.test(value.artifact_manifest_sha256)||!['staging','production'].includes(value.environment)||value.create_intent!==path.join(path.dirname(file),'create-dispatch.intent.json'))throw Error('EXACT_EXISTING_PROTECTED_DOCS_GUARD_SCOPE_REQUIRED');
 const parent=fs.lstatSync(path.dirname(file));if(!parent.isDirectory()||parent.isSymbolicLink()||(parent.mode&0o077))throw Error('PRIVATE_OPERATION_DIRECTORY_REQUIRED');
 return value;
}
function guardedDispatcher(dispatcher,cfg){
 const base='/client/v4/accounts/'+cfg.account_id+'/pages/projects/'+cfg.project;
 const allowedGet=new Set([base,base+'/upload-token']);
 const assetPosts=new Set(['/client/v4/pages/assets/check-missing','/client/v4/pages/assets/upload','/client/v4/pages/assets/upsert-hashes']);
 return {
  dispatch(options,handler){
   const origin=new URL(String(options.origin)),url=new URL(options.path,origin);
   const method=String(options.method||'GET').toUpperCase();
   if(origin.origin!=='https://api.cloudflare.com'||origin.href!==origin.origin+'/'||origin.username||origin.password||url.origin!==origin.origin||url.username||url.password||url.hash||/[\\]/.test(options.path)||options.path.split(/[/?]/).includes('..'))throw Error('FIXED_CLOUDFLARE_PROVIDER_ONLY');
   let allowed=method==='GET'&&(allowedGet.has(url.pathname)||url.pathname===base+'/deployments'||new RegExp('^'+base+'/deployments/[a-f0-9-]{36}$').test(url.pathname));
   allowed ||= method==='POST'&&assetPosts.has(url.pathname)&&!url.search;
   if(method==='POST'&&url.pathname===base+'/deployments'&&!url.search){
    // O_EXCL commits before the dispatcher can touch the network. An ambiguous
    // response, process interruption or new CLI cannot reset or reuse the budget.
    durable(cfg.create_intent,{schema_version:1,operation_id:cfg.operation_id,source_commit:cfg.source_commit,artifact_manifest_sha256:cfg.artifact_manifest_sha256,environment:cfg.environment,method,path:url.pathname,provider_create_budget:1,automatic_retry:false});
    allowed=true;
   }
   if(!allowed)throw Error('UNAPPROVED_PROVIDER_METHOD_OR_PATH');
   return dispatcher.dispatch(options,handler);
  },
  close:callback=>dispatcher.close(callback),
  destroy:(error,callback)=>dispatcher.destroy(error,callback),
 };
}
function install(){
 const config=configuration(process.env.ONESA_CF_GUARD_CONFIG,process.env.ONESA_CF_GUARD_SHA256);
 const undici=require('undici');
 const dispatcher=guardedDispatcher(undici.getGlobalDispatcher(),config);
 undici.setGlobalDispatcher(dispatcher);
 // Both APIs are used by the pinned bundled client and Node. Replacement must
 // fail rather than silently remove the transport gate later in startup.
 for(const version of [1,2])Object.defineProperty(globalThis,Symbol.for('undici.globalDispatcher.'+version),{value:dispatcher,writable:false,enumerable:false,configurable:false});
}
module.exports={configuration,guardedDispatcher};
if(process.env.ONESA_CF_GUARD_CONFIG)install();
