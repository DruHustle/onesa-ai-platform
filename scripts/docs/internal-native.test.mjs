import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {protectedDocsOrigin,protectedHeaders,verifyProtectedAssets,verifyAnonymousProtectedAssets,verifyProtectedRollback} from './internal-native.mjs';
const preview='https://1234abcd.onesa-engineering-docs.pages.dev',canonical='https://docs.engineering.onesa.eu';
const origins=[canonical,'https://onesa-engineering-docs.pages.dev',preview],team='https://existing-team.cloudflareaccess.com';
const body=Buffer.from('synthetic protected fixture, no private data');
const assets=Array.from({length:100},(_,i)=>({route:'/fixture-'+i,sha256:createHash('sha256').update(body).digest('hex'),bytes:body.length,mimes:['text/plain']}));
const headers={'content-type':'text/plain','cache-control':'private, no-store','x-robots-tag':'noindex, nofollow','x-content-type-options':'nosniff'};
const response=(status=200,value=body,extra={})=>({status:()=>status,body:async()=>value,headers:()=>({...headers,...extra})});

test('only the existing private canonical and actual Preview host can be observed',()=>{
 assert.equal(protectedDocsOrigin(canonical+'/','production'),canonical);
 assert.equal(protectedDocsOrigin(preview+'/','staging'),preview);
 for(const [url,env] of [[canonical+'/','staging'],[preview+'/','production'],['http://docs.engineering.onesa.eu/','production'],['https://other.pages.dev/','staging'],[canonical+'/private','production'],['https://user@docs.engineering.onesa.eu/','production'],[canonical+'/?code=fixture','production']])assert.throws(()=>protectedDocsOrigin(url,env));
});
test('every private byte is matched and has the actual no-store/noindex/nosniff headers',async()=>{
 let calls=0;const result=await verifyProtectedAssets(async()=>{calls++;return response();},canonical,assets);
 assert.equal(calls,100);assert.equal(result.verified,100);assert.equal(result.asset_security.length,100);
 assert.deepEqual(result.asset_security[0],{route:'/fixture-0',cache_control:'private, no-store',robots:'noindex, nofollow',nosniff:'nosniff'});
});
test('a public cache, indexing, missing header, changed byte or refused owner session fails closed',async()=>{
 for(const change of [{'cache-control':'public, max-age=60'},{'x-robots-tag':'index'},{'x-content-type-options':''}]){
  assert.throws(()=>protectedHeaders({...headers,...change}));
  await assert.rejects(verifyProtectedAssets(async()=>response(200,body,change),canonical,assets));
 }
 await assert.rejects(verifyProtectedAssets(async()=>response(200,Buffer.from('changed')),canonical,assets));
 await assert.rejects(verifyProtectedAssets(async()=>response(403),canonical,assets));
});
test('all asset aliases use a separate anonymous GET without redirect following or retry',async()=>{
 const calls=[];
 const result=await verifyAnonymousProtectedAssets(async(url,options)=>{calls.push({url,options});return response(302,Buffer.alloc(0),{location:team+'/cdn-cgi/access/login/owned-host?synthetic=1'});},origins,assets,team);
 assert.equal(result.length,300);assert.equal(new Set(calls.map(x=>x.url)).size,300);
 assert.ok(calls.every(x=>JSON.stringify(x.options)===JSON.stringify({maxRedirects:0,maxRetries:0,timeout:15000})));
 assert.ok(result.every(x=>x.http_status===302&&!x.followed_redirect&&x.redirect_origin===team));
 assert.ok(!JSON.stringify(result).includes('synthetic=1'));
});
test('anonymous success, not-found, foreign redirect and incomplete transport are never acceptance',async()=>{
 for(const [status,location] of [[200,null],[404,null],[302,'https://attacker.example.invalid/'],[302,team+'/other'],[302,'https://user@existing-team.cloudflareaccess.com/cdn-cgi/access/login/host']])await assert.rejects(verifyAnonymousProtectedAssets(async()=>response(status,body,{location}),origins,assets,team));
 await assert.rejects(verifyAnonymousProtectedAssets(async()=>{throw Error('synthetic interrupted GET');},origins,assets,team));
});
test('wrong account hosts, duplicate/missing assets and unsafe paths are rejected before any request',async()=>{
 let calls=0;const get=async()=>{calls++;return response(403);};
 for(const options of [origins.slice(0,2),[canonical,origins[1],'https://other.pages.dev'],[canonical,canonical,preview]])await assert.rejects(verifyAnonymousProtectedAssets(get,options,assets,team));
 for(const entries of [assets.slice(0,99),[...assets,assets[0]],assets.map((x,i)=>i?x:{...x,route:'//foreign.example.invalid/'})])await assert.rejects(verifyAnonymousProtectedAssets(get,origins,entries,team));
 assert.equal(calls,0);
});

const oldSource='d'.repeat(40),oldIndex=Buffer.from('<main>Retained synthetic private artifact</main>'),oldProvenance=Buffer.from(JSON.stringify({revision:oldSource,classification:'internal'}));
const rollback={deployment_id:'1234abcd-1111-4111-8111-111111111111',source:oldSource,index_sha256:createHash('sha256').update(oldIndex).digest('hex'),provenance_sha256:createHash('sha256').update(oldProvenance).digest('hex')};
test('retained rollback reads both exact private bytes on the existing canonical origin',async()=>{
 const calls=[];const result=await verifyProtectedRollback(async url=>{calls.push(url);return response(200,url.endsWith('.json')?oldProvenance:oldIndex);},rollback);
 assert.deepEqual(calls,[canonical+'/',canonical+'/generated/provenance.json']);
 assert.deepEqual(result,{...rollback,origin:canonical,private_headers:true,index_and_provenance_read_back:true,classification:'internal',provider_writes:0});
});
test('wrong rollback bytes, source, public headers, status or unbounded target are refused',async()=>{
 for(const get of [async()=>response(403),async()=>response(200,Buffer.from('changed')),async url=>response(200,url.endsWith('.json')?oldProvenance:oldIndex,{'cache-control':'public'})])await assert.rejects(verifyProtectedRollback(get,rollback));
 const get=async url=>response(200,url.endsWith('.json')?oldProvenance:oldIndex);
 await assert.rejects(verifyProtectedRollback(get,{...rollback,source:'e'.repeat(40)}));
 await assert.rejects(verifyProtectedRollback(get,{...rollback,origin:'https://foreign.example.invalid'}));
 await assert.rejects(verifyProtectedRollback(get,{...rollback,index_sha256:'wrong'}));
});
