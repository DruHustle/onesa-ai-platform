const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto'),{spawn}=require('node:child_process');
const {createGuard}=require('./oracle_vercel_transport_guard.cjs');
const modulePath=path.join(__dirname,'oracle_vercel_transport_guard.cjs');
function fixture(){const p=fs.mkdtempSync(path.join(os.tmpdir(),'onesa-transport-test-'));fs.chmodSync(p,0o700);fs.writeFileSync(path.join(p,'scope.json'),JSON.stringify({request_budget:1,operation_id:crypto.randomUUID(),repository:'DruHustle/onesa-ai-platform',component:'frontend',environment:'staging'}),{mode:0o600});return p;}
function child(code){return new Promise((resolve,reject)=>{const p=spawn(process.execPath,['-e',code],{stdio:'ignore'});p.on('error',reject);p.on('exit',code=>resolve(code));});}
test('the create budget survives process interruption and rejects a foreign target',()=>{
 const p=fixture();try{let check=createGuard(p);assert.throws(()=>check('https://foreign.invalid','POST','/v13/deployments'));check('https://api.vercel.com','POST','/v13/deployments?teamId=fixture');check('https://api.vercel.com','POST','/v2/files');check('https://api.vercel.com','GET','/v13/deployments');check=createGuard(p);assert.throws(()=>check('https://api.vercel.com','POST','/v13/deployments'));assert.equal(JSON.parse(fs.readFileSync(path.join(p,'create-request.json'))).automatic_retry,false);}finally{fs.rmSync(p,{recursive:true});}
});
test('simultaneous processes reserve one create atomically',async()=>{
 const p=fixture();try{const code=`try{require(${JSON.stringify(modulePath)}).createGuard(${JSON.stringify(p)})('https://api.vercel.com','POST','/v13/deployments');process.exit(0)}catch{process.exit(73)}`;const codes=await Promise.all([child(code),child(code)]);assert.deepEqual(codes.sort(),[0,73]);}finally{fs.rmSync(p,{recursive:true});}
});
for(const kind of ['fetch','http'])test(`${kind} transport cannot send a second deployment create`,async()=>{
 const p=fixture();let count=0;const server=http.createServer((req,res)=>{count++;req.resume();res.writeHead(201,{'Content-Type':'application/json'});res.end('{}');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
 try{const request=kind==='fetch'?`await fetch(${JSON.stringify(origin+'/v13/deployments')},{method:'POST',body:'{}'})`:`await new Promise((resolve,reject)=>{const r=require('node:http').request(${JSON.stringify(origin+'/v13/deployments')},{method:'POST'},res=>{res.resume();res.on('end',resolve)});r.on('error',reject);r.end('{}')})`;
 const code=`require(${JSON.stringify(modulePath)}).install(${JSON.stringify(p)},${JSON.stringify(origin)});(async()=>{${request};${request};process.exit(0)})().catch(()=>process.exit(2));`;
 assert.equal(await child(code),73);assert.equal(count,1);
 }finally{await new Promise(resolve=>server.close(resolve));fs.rmSync(p,{recursive:true});}
});
