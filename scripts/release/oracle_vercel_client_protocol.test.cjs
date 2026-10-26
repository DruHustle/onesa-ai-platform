// Exercise the real pinned CLI's prebuilt client offline, with no provider token.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),http=require('node:http');
const crypto=require('node:crypto'),assert=require('node:assert/strict');
async function fixture(mode){
 const cli='/opt/onesa-vercel-tool/node_modules/vercel';
 assert.equal(JSON.parse(fs.readFileSync(path.join(cli,'package.json'))).version,'65.2.0');
 const chunks=path.join(cli,'dist/chunks');
 const entries=fs.readdirSync(chunks).filter(n=>n.endsWith('.js')&&fs.readFileSync(path.join(chunks,n),'utf8').includes('"../client/dist/create-deployment.js"'));
 assert.equal(entries.length,1);
 const {require_dist}=await import('file://'+path.join(chunks,entries[0]));
 const {createDeployment}=require_dist();
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'onesa-real-client-'));fs.chmodSync(directory,0o700);
 const transport=path.join(directory,'transport'),workspace=path.join(directory,'workspace');fs.mkdirSync(transport,{mode:0o700});
 fs.mkdirSync(path.join(workspace,'.vercel/output/static'),{recursive:true});
 fs.writeFileSync(path.join(workspace,'.vercel/output/config.json'),'{"version":3}');
 fs.writeFileSync(path.join(workspace,'.vercel/output/static/owned.js'),'console.log("credential-free protocol fixture");');
 fs.writeFileSync(path.join(transport,'scope.json'),JSON.stringify({request_budget:1,operation_id:crypto.randomUUID(),repository:'DruHustle/onesa-ai-platform',component:'frontend',environment:'staging'}),{mode:0o600});
 const uploaded=new Set();let posts=0,created=0,uploads=0;const errors=[];
 const server=http.createServer(async(req,res)=>{
  try{
   const chunks=[];for await(const chunk of req)chunks.push(chunk);const bytes=Buffer.concat(chunks);
   if(req.method==='POST'&&req.url.startsWith('/v2/files')){
    assert.equal(crypto.createHash('sha1').update(bytes).digest('hex'),req.headers['x-now-digest']);uploaded.add(req.headers['x-now-digest']);uploads++;res.writeHead(200);res.end('{}');return;
   }
   assert.equal(req.method,'POST');assert.ok(req.url.startsWith('/v13/deployments'));posts++;
   const body=JSON.parse(bytes);assert.ok(body.files.length);const missing=body.files.map(f=>f.sha).filter(sha=>!uploaded.has(sha));
   if(mode==='cold'&&missing.length){res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{code:'missing_files',missing}}));return;}
   created++;assert.equal(created,1);res.writeHead(201,{'Content-Type':'application/json'});res.end(JSON.stringify({id:'dpl_fixture',readyState:'READY',aliasAssigned:true,url:'fixture.invalid'}));
  }catch(e){errors.push(e.message);res.writeHead(500);res.end('{}');}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
 require('./oracle_vercel_transport_guard.cjs').install(transport,origin);
 try{
  const events=[];for await(const event of createDeployment({path:workspace,vercelOutputDir:path.join(workspace,'.vercel/output'),prebuilt:true,token:'synthetic-loopback-only',apiUrl:origin},{name:'onesa-protocol-fixture'})){
   if(event.type==='error')throw Error('Pinned client failed: '+event.payload.code);events.push(event.type);
  }
  assert.deepEqual(errors,[]);assert.equal(created,1);assert.equal(posts,mode==='cold'?2:1);assert.equal(uploads>0,mode==='cold');assert.ok(events.includes('alias-assigned'));
  assert.equal(fs.existsSync(path.join(transport,'missing-files-response.json')),mode==='cold');assert.equal(fs.existsSync(path.join(transport,'create-continuation-request.json')),mode==='cold');
  console.log(JSON.stringify({cli:'65.2.0',mode,deployment_post_requests:posts,actual_creates:created,file_uploads:uploads,network:'loopback-only',provider_credentials:false}));
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.rmSync(directory,{recursive:true});}
}
if(process.argv[2]==='--fixture')fixture(process.argv[3]).catch(e=>{console.error(e);process.exit(1)});
else{
 const test=require('node:test'),{execFile}=require('node:child_process');
 for(const mode of ['cold','warm'])test(`pinned prebuilt client ${mode} cache creates exactly one deployment`,{timeout:30000},async()=>{
  const result=await new Promise((resolve,reject)=>execFile(process.execPath,[__filename,'--fixture',mode],{timeout:25000,env:{PATH:process.env.PATH}},(error,stdout,stderr)=>error?reject(Error(stderr||error.message)):resolve(JSON.parse(stdout))));
  assert.equal(result.actual_creates,1);assert.equal(result.provider_credentials,false);
 });
}
