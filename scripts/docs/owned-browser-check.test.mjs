import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {runOwnedBrowserCheck} from './owned-browser-check.mjs';

test('fixture completion, assertion failure and a stalled browser descendant remain distinct',async t=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'onesa-owned-browser-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 async function run(name,source,timeoutMs=3000){const file=path.join(dir,name+'.mjs');await fs.writeFile(file,source);return runOwnedBrowserCheck(pathToFileURL(file),{timeoutMs});}
 assert.deepEqual(await run('success','process.exitCode=0'),{code:0,timedOut:false});
 assert.deepEqual(await run('failed','process.exitCode=7'),{code:1,timedOut:false});
 const pidFile=path.join(dir,'descendant.pid');
 const source=`import {spawn} from 'node:child_process';import fs from 'node:fs';const child=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'ignore'});fs.writeFileSync(${JSON.stringify(pidFile)},String(child.pid));setInterval(()=>{},1000);`;
 const started=Date.now();assert.deepEqual(await run('stalled',source,1000),{code:1,timedOut:true});assert.ok(Date.now()-started<5000);
 const pid=Number(await fs.readFile(pidFile,'utf8'));
 // A killed child can briefly remain a zombie while the OS reaps it; it cannot run.
 let active=false;
 for(let i=0;i<20;i++){
  try{process.kill(pid,0);active=true;}catch(error){assert.equal(error.code,'ESRCH');active=false;break;}
  if(process.platform==='linux'){const state=await fs.readFile(`/proc/${pid}/stat`,'utf8').catch(()=>null);if(!state||state.split(' ')[2]==='Z'){active=false;break;}}
  await new Promise(resolve=>setTimeout(resolve,50));
 }
 assert.equal(active,false,'The fixture browser descendant must be stopped');
});
