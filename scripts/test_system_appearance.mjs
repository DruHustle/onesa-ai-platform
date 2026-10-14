import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
const manifest=JSON.parse(fs.readFileSync('docs/engineering/design-system.consumer.json','utf8'));
const chat='onesa-ai-platform-frontend/apps/chat/src/app/';
const docs='onesa-ai-platform-frontend/apps/docs/';
test('pinned independent artifacts implement system preference with readable fallback',()=>{
  assert.equal(manifest.version,'1.0.0');
  for(const artifact of manifest.local_artifacts){
    const css=fs.readFileSync(artifact,'utf8');
    assert.equal(crypto.createHash('sha256').update(css).digest('hex'),manifest.sha256);
    assert.match(css,/:root\s*\{\s*color-scheme:\s*light;/);
    assert.match(css,/@media\s*\(prefers-color-scheme:\s*dark\)/);
    assert.match(css,/color-scheme:\s*dark;/);
    assert.match(css,/@media\s*\(forced-colors:\s*active\)/);
    assert.match(css,/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
    assert.match(css,/@media\s*print/);
  }
});
test('no application clocks or persisted appearance overrides remain in active implementations',()=>{
  const files=[chat+'layout.tsx',chat+'globals.css',docs+'docusaurus.config.ts',docs+'src/css/custom.css',docs+'src/theme/Root/index.tsx'];
  for(const file of files){const source=fs.readFileSync(file,'utf8');assert.doesNotMatch(source,/dayNightBoot|OnesaDayNight|getHours\(|automatic-day-night|suppressHydrationWarning|localStorage.*theme|setInterval\(/,file);}
  assert.match(fs.readFileSync(docs+'docusaurus.config.ts','utf8'),/respectPrefersColorScheme:true,disableSwitch:true/);
  assert.equal(fs.existsSync(chat+'../lib/day-night-boot.ts'),false);
  assert.equal(fs.existsSync(docs+'static/automatic-day-night.js'),false);
});
function luminance(hex){return hex.match(/[\da-f]{2}/gi).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);}
function contrast(a,b){const values=[luminance(a),luminance(b)].sort((x,y)=>y-x);return(values[0]+.05)/(values[1]+.05);}
test('shared text and product actions satisfy measured contrast in light and dark',()=>{
  const pairs=[['text-light','#10263e','#ffffff'],['muted-light','#56677b','#f5f7fa'],['text-dark','#e5edf6','#0b1523'],['muted-dark','#b4c4d6','#14243a'],['ai-action-light','#ffffff','#4f46e5'],['ai-action-dark','#0b1523','#c4b5fd'],['docs-link-light','#1d4ed8','#f5f7fa'],['docs-link-dark','#9bc8ff','#14243a'],['error-light','#912b2b','#fceaea'],['error-dark','#ffd1d1','#392626']];
  for(const [role,fg,bg] of pairs)assert.ok(contrast(fg,bg)>=4.5,`${role}: ${contrast(fg,bg).toFixed(2)}`);
  for(const [role,fg,bg] of [['border-light','#6e7d90','#f5f7fa'],['border-dark','#7592ac','#14243a']])assert.ok(contrast(fg,bg)>=3,`${role}: ${contrast(fg,bg).toFixed(2)}`);
});
test('product navigation is an immutable four-product contract',()=>{
 for(const artifact of manifest.applications.local_artifacts){const bytes=fs.readFileSync(artifact);assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),manifest.applications.sha256);const products=JSON.parse(bytes).applications;assert.deepEqual(products.map(p=>p.label),['Onesa UG','Onesa AI Platform','Onesa AI Robot','Onesa Developer Docs']);assert.equal(new Set(products.map(p=>p.href)).size,4);}
});
test('approved product icon derivatives retain pinned provenance and safe small-size formats',()=>{
 assert.equal(manifest.identity_icons.version,'1.0.0');
 const svgHashes=[];
 for(const artifact of manifest.identity_icons.local_artifacts){
  const sourceBytes=fs.readFileSync(artifact.manifest);
  assert.equal(crypto.createHash('sha256').update(sourceBytes).digest('hex'),artifact.sha256);
  const source=JSON.parse(sourceBytes);
  assert.equal(source.sourceSha256,manifest.identity_icons.source_sha256);
  assert.equal(source.sourceRepository,manifest.identity_icons.owner);
  assert.equal(source.products.length,1);
  assert.equal(source.products[0].id,artifact.product);
  for(const file of source.products[0].files){
   assert.equal(path.basename(file.name),file.name);
   const bytes=fs.readFileSync(path.join(path.dirname(artifact.manifest),file.name));
   assert.equal(bytes.length,file.bytes);
   assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),file.sha256);
   if(file.mime==='image/svg+xml'){
    const svg=bytes.toString('utf8');
    assert.match(svg,/viewBox="0 0 32 32"/);
    assert.doesNotMatch(svg.replace('xmlns="http://www.w3.org/2000/svg"',''),/<script|<foreignObject|\b(?:href|onload|onclick|src)\s*=|url\s*\(|https?:\/\//i);
    svgHashes.push(file.sha256);
   }else if(file.mime==='image/png'){
    assert.equal(bytes.subarray(1,4).toString(),'PNG');
    assert.equal(bytes.readUInt32BE(16),file.width);assert.equal(bytes.readUInt32BE(20),file.height);
   }else{
    assert.equal(file.mime,'image/vnd.microsoft.icon');assert.equal(bytes.readUInt16LE(2),1);
    assert.equal(bytes.readUInt16LE(4),3);
    assert.deepEqual([0,1,2].map(index=>bytes[6+index*16]),[16,32,64]);
    const installed=fs.readFileSync(artifact.product==='ai'?chat+'favicon.ico':docs+'static/favicon.ico');
    assert.equal(crypto.createHash('sha256').update(installed).digest('hex'),file.sha256);
   }
  }
 }
 assert.equal(new Set(svgHashes).size,2);
});
test('canonical design and management diagrams remain internal' ,()=>{
 const policy=JSON.parse(fs.readFileSync('docs/documentation-policy.json','utf8'));
 assert.equal(policy.default_classification,'internal');
 assert.ok(!policy.public_sources.includes('docs/architecture/ONESA_DESIGN_SYSTEM.md'));
 assert.ok(!policy.public_sources.includes('docs/operations/TAILSCALE_ADMINISTRATION.md'));
 for(const id of ['onesa-design-system','tailscale-administration'])assert.ok(!policy.public_diagrams.includes(id));
 for(const obsolete of ['CONTRIBUTING.md','SECURITY.md'])assert.equal(fs.existsSync(obsolete),false);
});
