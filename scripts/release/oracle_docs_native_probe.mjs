// Pinned native observer only. Its parent verifies the signed root challenge,
// exact source/runtime closure and input bytes before any signing key is read.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
let browser,anonymous;
try{
 const file=process.argv[2],pin=process.argv[3];
 if(!path.isAbsolute(file)||!/^[a-f0-9]{64}$/.test(pin))throw Error('PRIVATE_PINNED_INPUT_REQUIRED');
 const stat=await fs.lstat(file);
 if(!stat.isFile()||stat.isSymbolicLink()||stat.mode&0o077||stat.size>4*1024*1024)throw Error('PRIVATE_INPUT_CUSTODY');
 const raw=await fs.readFile(file);
 if(createHash('sha256').update(raw).digest('hex')!==pin)throw Error('VERIFIED_INPUT_CHANGED');
 const v=JSON.parse(raw.toString('utf8'));
 if(!path.isAbsolute(v.checkout)||path.basename(v.checkout)!=='onesa-ai-platform'||!/^[a-f0-9]{40}$/.test(v.revision)||!['staging','production'].includes(v.environment)||!['preflight','observe'].includes(v.mode))throw Error('EXACT_NATIVE_SOURCE_AND_MODE_REQUIRED');
 const require=createRequire(path.join(v.checkout,'onesa-ai-platform-frontend/apps/docs/package.json'));
 const {chromium,request}=require('@playwright/test');
 const internal=v.component==='docs-internal';
 if(v.component!==undefined&&!internal)throw Error('EXACT_NATIVE_DOCS_COMPONENT_REQUIRED');
 const module=await import(pathToFileURL(path.join(v.checkout,internal?'scripts/docs/internal-native.mjs':'scripts/docs/native-owner.mjs')));
 const origin=internal?module.protectedDocsOrigin(v.origin+'/',v.environment):module.exactNativeDocsOrigin(v.origin+'/',v.environment);
 browser=await chromium.connectOverCDP('http://127.0.0.1:19222',{timeout:15000});
 const browserSession=await browser.newBrowserCDPSession();
 let version;try{version=await browserSession.send('Browser.getVersion');}finally{await browserSession.detach();}
 if(typeof version.product!=='string'||!/^Chrome\/[0-9.]+$/.test(version.product)||typeof version.userAgent!=='string'||/HeadlessChrome/i.test(version.userAgent))throw Error('HEADED_OWNER_CHROME_REQUIRED');
 const browserIdentity={product:version.product,reported_headless:false,connection:'existing-owner-native-cdp'};
 if(browser.contexts().length!==1)throw Error('ISOLATED_OWNER_CONTEXT_REQUIRED');
 const context=browser.contexts()[0];
  if(!Array.isArray(v.assets)||v.assets.length<100||v.assets.length>20000||new Set(v.assets.map(x=>x.route)).size!==v.assets.length)throw Error('BOUNDED_TRUSTED_ASSET_MANIFEST_REQUIRED');
  for(const x of v.assets)if(typeof x.route!=='string'||!x.route.startsWith('/')||x.route.startsWith('//')||/[?#\\]/.test(x.route)||!/^[a-f0-9]{64}$/.test(x.sha256)||!Number.isSafeInteger(x.bytes)||x.bytes<0||x.bytes>16*1024*1024||!Array.isArray(x.mimes)||!x.mimes.length)throw Error('EXACT_ASSET_BYTES_AND_MIME_REQUIRED');
  let result;
  if(internal){
   // A new API context has no browser storage or existing owner credentials.
   // Never copy cookies, headers, profiles, JWTs or a browser request context.
   anonymous=await request.newContext({ignoreHTTPSErrors:false,timeout:15000,extraHTTPHeaders:{'Cache-Control':'no-cache'}});
   const registry=JSON.parse(await fs.readFile(path.join(v.checkout,'onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json'),'utf8'));
   const icons=JSON.parse(await fs.readFile(path.join(v.checkout,'onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json'),'utf8'));
   result=await module.validateNativeProtectedDocumentation(context,{origin,revision:v.revision,expectedEnvironment:v.environment,assets:v.assets,origins:v.origins,teamOrigin:v.team_origin,anonymousGet:(url,options)=>anonymous.get(url,options),registry,icons,rollback:v.rollback});
   if(v.mode==='preflight')result={state:'NATIVE_OWNER_SESSION_READY_NOT_QUALIFICATION',providerWrites:0,sessionValuesRead:false};
  }else{
   const validate=v.mode==='preflight'?module.validateNativePublicPreflight:module.validateNativePublicDocumentation;
   result=await validate(context,{origin,revision:v.revision,expectedEnvironment:v.environment,verifyPublicAssets:async get=>module.verifyNativePublicAssets(get,origin,v.assets)});
  }
  console.log(JSON.stringify(v.mode==='preflight'?result:{...result,browser:browserIdentity}));
}catch(error){
 console.error(JSON.stringify({state:'NATIVE_OBSERVATION_FAILED_NOT_QUALIFIED',category:error.name,guard:/^[A-Z0-9_]+$/.test(error.message)?error.message:'NATIVE_READ_OR_ASSERTION_FAILURE',providerWrites:0,sessionValuesRead:false}));process.exitCode=1;
}finally{
 await anonymous?.dispose();
 // For connectOverCDP, the pinned SDK closes its transport, not the owner browser.
 await browser?.close();
}
