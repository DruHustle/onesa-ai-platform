import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
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
test('canonical design and management diagrams remain internal' ,()=>{
 const policy=JSON.parse(fs.readFileSync('docs/documentation-policy.json','utf8'));
 assert.equal(policy.default_classification,'internal');
 assert.ok(!policy.public_sources.includes('docs/architecture/ONESA_DESIGN_SYSTEM.md'));
 assert.ok(!policy.public_sources.includes('docs/operations/TAILSCALE_ADMINISTRATION.md'));
 for(const id of ['onesa-design-system','tailscale-administration'])assert.ok(!policy.public_diagrams.includes(id));
 for(const obsolete of ['CONTRIBUTING.md','SECURITY.md'])assert.equal(fs.existsSync(obsolete),false);
});
