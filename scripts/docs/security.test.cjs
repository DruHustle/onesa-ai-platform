'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const {createRequire}=require('node:module');
const http=require('node:http');
const {callableConsumer,compatiblePatterns,boundedPattern}=require('../glob_security.cjs');
const root=path.resolve(__dirname,'../..');
const docsRequire=createRequire(path.join(root,'onesa-ai-platform-frontend/apps/docs/package.json'));
const braces=docsRequire('braces');
const {sprintf,vsprintf}=docsRequire('sprintf-js');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'packages/security/provenance.json'),'utf8'));
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');

test('GHSA-6pq8-jhm2-2vcw: comma arrays tolerate non-callable own toString values',()=>{
 const qs=docsRequire('qs');
 for(const options of [{arrayFormat:'comma'},{arrayFormat:'comma',encodeValuesOnly:true}]){
  for(const value of ['x',null,42,{}]){
   let result;
   assert.doesNotThrow(()=>{result=qs.stringify({a:[{toString:value}]},options);});
   assert.equal(typeof result,'string');
  }
  assert.equal(qs.stringify({a:['first','second']},options),options.encodeValuesOnly?'a=first,second':'a=first%2Csecond');
 }
 assert.deepEqual(qs.parse('a%5B0%5D=first&a%5B1%5D=second'),{a:['first','second']});
});

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
 checkConsumer('@svgr/plugin-svgo','deepmerge','deepmerge');
 checkConsumer('swagger-client','deepmerge','deepmerge');
 const remarkable=createRequire(docsRequire.resolve('remarkable/package.json'));
 const argparse=createRequire(remarkable.resolve('argparse/package.json'));
 const directory=path.dirname(argparse.resolve('sprintf-js/package.json'));
 assert.equal(JSON.parse(fs.readFileSync(path.join(directory,'package.json'))).name,'@onesa/sprintf-js');
 for(const [file,digest] of Object.entries(manifest['sprintf-js'].shipped_files)) assert.equal(hash(fs.readFileSync(path.join(directory,file))),digest);
 for(const [name,record] of Object.entries(manifest)){
  for(const [file,digest] of Object.entries(record.source_files)) assert.equal(hash(fs.readFileSync(path.join(root,'packages/security',name,file))),digest);
  assert.equal(hash(fs.readFileSync(path.join(root,record.archive))),record.archive_sha256);
  for(const archive of record.additional_archives||[]) assert.equal(hash(fs.readFileSync(path.join(root,archive))),record.archive_sha256);
 }
});

test('GHSA-g3hv-75wg-m249: installed Docs matchers bound amplification and preserve reviewed syntax',async()=>{
 const legacy=callableConsumer(docsRequire,'serve-handler');
 const swagger=createRequire(docsRequire.resolve('@swagger-api/apidom-reference'));
 assert.equal(swagger('minimatch/package.json').version,'11.0.1');
 for(const entry of [legacy,swagger.resolve('minimatch')]){
  compatiblePatterns(entry);
  await boundedPattern(entry);
 }
});

test('actual serve-handler preserves glob headers, redirects, rewrites and missing-file refusal',async t=>{
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'onesa-serve-compat-'));
 fs.mkdirSync(path.join(folder,'public'));
 fs.writeFileSync(path.join(folder,'public','guide.txt'),'synthetic public guide');
 const handler=docsRequire('serve-handler');
 const server=http.createServer((request,response)=>handler(request,response,{
  public:path.join(folder,'public'),cleanUrls:false,directoryListing:false,
  headers:[{source:'**/*.txt',headers:[{key:'X-Onesa-Fixture',value:'matched'}]}],
  redirects:[{source:'/legacy',destination:'/guide.txt',type:302}],
  rewrites:[{source:'/help',destination:'/guide.txt'}],
 }));
 t.after(async()=>{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.rmSync(folder,{recursive:true,force:true});});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base=`http://127.0.0.1:${server.address().port}`;
 for(const route of ['/guide.txt','/help']){
  const response=await fetch(base+route);
  assert.equal(response.status,200);assert.equal(await response.text(),'synthetic public guide');
 }
 assert.equal((await fetch(base+'/guide.txt')).headers.get('x-onesa-fixture'),'matched');
 const redirected=await fetch(base+'/legacy',{redirect:'manual'});
 assert.equal(redirected.status,302);assert.equal(redirected.headers.get('location'),'/guide.txt');
 assert.equal((await fetch(base+'/missing.txt')).status,404);
});

test('actual Swagger file resolver preserves explicit allowlists and defaults to refusal',()=>{
 const FileResolver=docsRequire('@swagger-api/apidom-reference/resolve/resolvers/file').default;
 const resolver=new FileResolver({fileAllowList:['/owned/docs/**/*.yaml']});
 assert.equal(resolver.canRead({uri:'/owned/docs/api/schema.yaml'}),true);
 for(const uri of ['/owned/private/key.yaml','/owned/docs/schema.json','https://unowned.invalid/schema.yaml']) assert.equal(resolver.canRead({uri}),false);
 assert.equal(new FileResolver().canRead({uri:'/owned/docs/schema.yaml'}),false);
});

for(const entry of ['deepmerge','deepmerge/dist/umd.js']){
 const merge=docsRequire(entry);
 test(`GHSA-gcqx-w48m-w2h4: ${entry} preserves prototypes for hostile source and target shapes`,()=>{
  const payload=()=>JSON.parse('{"__proto__":{"onesaUnownedAdmin":true}}');
  const nullTarget=Object.assign(Object.create(null),{debug:false});
  const cases=[
   [nullTarget,payload(),value=>value],
   [payload(),{verbose:true},value=>value],
   [{list:[]},{list:[payload()]},value=>value.list[0]],
   ...[null,undefined,0,false,'placeholder'].map(session=>[{session},{session:payload()},value=>value.session]),
  ];
  for(const [target,source,select] of cases){
   const result=merge(target,source);const observed=select(result);
   assert.equal(Object.getPrototypeOf(observed),Object.prototype);
   assert.equal(Object.hasOwn(observed,'__proto__'),false);
   assert.equal(observed.onesaUnownedAdmin,undefined);
   assert.equal(({}).onesaUnownedAdmin,undefined);
  }
  assert.equal(nullTarget.debug,false);
  assert.equal(Object.getPrototypeOf(nullTarget),null);
  assert.equal(merge(nullTarget,payload()).debug,false);
 });
 test(`${entry} rejects dangerous keys before reading their getters`,()=>{
  let reads=0;const hostile={};
  Object.defineProperty(hostile,'__proto__',{enumerable:true,get(){reads++;throw new Error('must never read this key');}});
  assert.deepEqual(merge(hostile,{valid:true}),{valid:true});
  assert.deepEqual(merge(Object.create(null),hostile),{});
  assert.equal(reads,0);
 });
 test(`${entry} retains nested merges, symbols, arrays and custom merge compatibility`,()=>{
  const symbol=Symbol('metadata');const target={nested:{a:1},list:[{id:1}],[symbol]:{a:1}};
  const source={nested:{b:2},list:[{id:2}],[symbol]:{b:2}};const merged=merge(target,source);
  assert.deepEqual(merged.nested,{a:1,b:2});assert.deepEqual(merged.list,[{id:1},{id:2}]);
  assert.deepEqual(merged[symbol],{a:1,b:2});assert.notEqual(merged.list[0],target.list[0]);
  assert.deepEqual(merge.all([{a:1},{b:2}]),{a:1,b:2});
  assert.deepEqual(merge({list:[1]},{list:[2]},{arrayMerge:(_target,input)=>input}),{list:[2]});
  assert.deepEqual(merge({label:{value:'a'}},{label:{value:'b'}},{customMerge:key=>key==='label'?(_a,b)=>({value:b.value.toUpperCase()}):undefined}),{label:{value:'B'}});
  assert.deepEqual(target.nested,{a:1});
 });
}

test('real Swagger resolution/request generation and SVGR transformation retain compatibility',async()=>{
 const Swagger=docsRequire('swagger-client');
 const spec={openapi:'3.0.3',info:{title:'Synthetic',version:'1.0'},servers:[{url:'https://synthetic.invalid'}],paths:{'/widgets/{id}':{get:{operationId:'getWidget',parameters:[{name:'id',in:'path',required:true,schema:{type:'string'}}],responses:{200:{description:'Owned fixture'}}}}}};
 const resolved=await Swagger.resolve({spec});assert.deepEqual(resolved.errors,[]);
 const request=Swagger.buildRequest({spec:resolved.spec,operationId:'getWidget',parameters:{id:'owned'}});
 assert.equal(request.url,'https://synthetic.invalid/widgets/owned');assert.equal(request.method,'GET');
 const transform=docsRequire('@svgr/plugin-svgo');
 const svg=transform('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0h10v10H0z"/></svg>',{svgo:true},{componentName:'SyntheticIcon'});
 assert.match(svg,/<svg/);assert.match(svg,/viewBox="0 0 10 10"/);
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
