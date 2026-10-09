'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const {createRequire}=require('node:module');
const root=path.resolve(__dirname,'../..');
const docsRequire=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/docs/package.json'));
const braces=docsRequire('braces');
const {sprintf,vsprintf}=docsRequire('sprintf-js');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'packages/security/provenance.json'),'utf8'));
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');

function checkConsumer(parent,dependency,name){
 const consumer=createRequire(docsRequire.resolve(parent+'/package.json'));
 const directory=path.dirname(consumer.resolve(dependency+'/package.json'));
 const meta=JSON.parse(fs.readFileSync(path.join(directory,'package.json'),'utf8'));
 assert.equal(meta.name,'@onesa/'+name);
 for(const [file,digest] of Object.entries(manifest[name].shipped_files)){
  assert.equal(hash(fs.readFileSync(path.join(directory,file))),digest,`${parent}: installed ${file} matches reviewed backport`);
 }
}

test('every affected transitive consumer uses the reviewed local fixes',()=>{
 checkConsumer('micromatch','braces','braces');
 checkConsumer('chokidar','braces','braces');
 const remarkable=createRequire(docsRequire.resolve('remarkable/package.json'));
 const argparse=createRequire(remarkable.resolve('argparse/package.json'));
 const directory=path.dirname(argparse.resolve('sprintf-js/package.json'));
 assert.equal(JSON.parse(fs.readFileSync(path.join(directory,'package.json'))).name,'@onesa/sprintf-js');
 for(const [file,digest] of Object.entries(manifest['sprintf-js'].shipped_files)) assert.equal(hash(fs.readFileSync(path.join(directory,file))),digest);
 for(const [name,record] of Object.entries(manifest)){
  for(const [file,digest] of Object.entries(record.source_files)) assert.equal(hash(fs.readFileSync(path.join(root,'packages/security',name,file))),digest);
  assert.equal(hash(fs.readFileSync(path.join(root,record.archive))),record.archive_sha256);
 }
});

for(const method of ['parse','compile','expand','stringify']){
 test(`GHSA-vfj7-8cjw-p6xm: ${method} rejects deep braces and parentheses before recursion`,()=>{
  for(const [left,right] of [['{','}'],['(',')']]){
   const hostile=left.repeat(4000)+'x'+right.repeat(4000);
   assert.throws(()=>braces[method](hostile,{maxDepth:Infinity}),error=>error.code==='ERR_BRACES_MAX_DEPTH'&&!/call stack/i.test(error.message));
   assert.throws(()=>braces[method](left.repeat(4000)+'x'),error=>error.code==='ERR_BRACES_MAX_DEPTH');
  }
 });
}
for(const method of ['compile','expand','stringify']){
 test(`${method} rejects direct deep/cyclic AST input while allowing parent back-links`,()=>{
  let ast={type:'text',value:'x'};
  for(let i=0;i<10000;i++)ast={type:'root',nodes:[ast]};
  assert.throws(()=>braces[method](ast),error=>error.code==='ERR_BRACES_MAX_DEPTH');
  const cycle={type:'root',nodes:[]};cycle.nodes.push(cycle);
  assert.throws(()=>braces[method](cycle),error=>error.code==='ERR_BRACES_MAX_DEPTH');
  assert.doesNotThrow(()=>braces[method](braces.parse('docs/{api,guide}.md')));
 });
}

test('normal brace APIs, nesting, escapes, range bounds and real micromatch remain compatible',()=>{
 assert.deepEqual(braces.expand('docs/{api,guide}.{md,mdx}'),['docs/api.md','docs/api.mdx','docs/guide.md','docs/guide.mdx']);
 assert.deepEqual(braces.expand('v{1..3}'),['v1','v2','v3']);
 assert.deepEqual(braces.expand('v{03..01}'),['v03','v02','v01']);
 assert.deepEqual(braces.expand('{a,{b,c}}'),['a','b','c']);
 assert.deepEqual(braces.expand('a\\{b,c\\}'),['a{b,c}']);
 assert.equal(braces.compile('docs/{api,guide}.md'),'docs/(api|guide).md');
 assert.equal(braces.stringify(braces.parse('docs/{api,guide}.md')),'docs/{api,guide}.md');
 assert.doesNotThrow(()=>braces.compile('{'.repeat(64)+'a'+'}'.repeat(64)));
 assert.throws(()=>braces.expand('{1..1001}'),/range limit/);
 const mm=docsRequire('micromatch');
 assert.deepEqual(mm(['docs/a.md','docs/b.mdx','docs/c.txt','src/a.md'],'docs/**/*.{md,mdx}'),['docs/a.md','docs/b.mdx']);
 assert.deepEqual(braces(['{a,b}','{c,d}'],{expand:true}),['a','b','c','d']);
});

test('chokidar actually discovers and watches brace-glob documentation files',async t=>{
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'onesa-security-watch-'));
 fs.mkdirSync(path.join(folder,'docs'));fs.writeFileSync(path.join(folder,'docs/a.md'),'a');fs.writeFileSync(path.join(folder,'docs/ignored.txt'),'ignored');
 const watcher=docsRequire('chokidar').watch(path.join(folder,'docs/*.{md,mdx}'),{ignoreInitial:false});
 t.after(async()=>{await watcher.close();fs.rmSync(folder,{recursive:true,force:true});});
 const initial=[];watcher.on('add',p=>initial.push(path.basename(p)));
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('watch readiness timed out')),5000);watcher.once('error',reject);watcher.once('ready',()=>{clearTimeout(timer);resolve();});});
 assert.deepEqual(initial,['a.md']);
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('watch update timed out')),5000);watcher.on('add',p=>{if(path.basename(p)==='new.mdx'){clearTimeout(timer);resolve();}});fs.writeFileSync(path.join(folder,'docs/new.mdx'),'new');});
});

test('GHSA-hp3w-g68c-fv3c: hostile numeric precision and width produce bounded output without native failure',()=>{
 for(const type of ['e','f','g']){
  for(const digits of ['101','999999999','9'.repeat(300)]){
   const result=sprintf('%.'+digits+type,1.2345);
   assert.equal(typeof result,'string');assert.ok(result.length<120);
  }
 }
 assert.equal(sprintf('%.0f',1.7),'2');
 assert.equal(sprintf('%.0g',1.7),'2');
 assert.ok(sprintf('%999999999f',1.2).length<=10000);
 assert.equal(sprintf('%.2f',1.25),'1.25');
});

test('valid sprintf/vsprintf, named parameters, flags and real argparse/Remarkable remain compatible',()=>{
 assert.equal(sprintf('%s: %04d','port',42),'port: 0042');
 assert.equal(sprintf('%(user.name)s',{user:{name:'Onesa'}}),'Onesa');
 assert.equal(vsprintf('%s %.2f',['API',1.25]),'API 1.25');
 assert.equal(sprintf('%+08.2f',1.25),'+0001.25');
 assert.equal(sprintf('%.0e',1.25),'1e+0');
 assert.equal(sprintf('%.2s','Onesa'),'On');
 assert.equal(sprintf('%.2f %.2f',1.25,2.5),'1.25 2.50');
 const remarkable=createRequire(docsRequire.resolve('remarkable/package.json'));
 const {ArgumentParser}=remarkable('argparse');
 const parser=new ArgumentParser({prog:'onesa-docs',addHelp:false});
 parser.addArgument(['--port'],{type:'int',defaultValue:3200,help:'Port (default %(defaultValue)s)'});
 assert.equal(parser.parseArgs(['--port','3201']).port,3201);
 assert.match(parser.formatHelp(),/3200/);
 const {Remarkable}=docsRequire('remarkable');
 assert.match(new Remarkable().render('# Onesa\n\n**API** docs'),/<strong>API<\/strong>/);
});


test('documentation search refuses access-denied HTML before parsing JSON',async()=>{
 const source=fs.readFileSync(path.join(root,'onesa-ai-platform-frontend/apps/docs/src/lib/search-index.ts'),'utf8');
 const code=docsRequire('esbuild').transformSync(source,{loader:'ts',format:'cjs'}).code;
 const fixture={exports:{}};
 new Function('module','exports',code)(fixture,fixture.exports);
 const {readSearchIndex}=fixture.exports;
 for(const status of [401,403,503]) {
  let parsed=false;
  await assert.rejects(readSearchIndex({ok:false,headers:new Headers({'content-type':'text/html'}),json:async()=>{parsed=true;throw new Error('HTML is not JSON');}}),/search is unavailable/);
  assert.equal(parsed,false,`HTTP ${status} HTML must not be parsed`);
 }
 const entries=[{title:'Authentication',url:'/docs/public/authentication',text:'Sessions'}];
 assert.deepEqual(await readSearchIndex(Response.json(entries)),entries);
 await assert.rejects(readSearchIndex(Response.json({error:'denied'})),/search is unavailable/);
});
