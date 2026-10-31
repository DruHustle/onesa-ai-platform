import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const manifest={};
const packages={braces:{upstream_version:'3.0.3',advisory:'GHSA-vfj7-8cjw-p6xm'},'sprintf-js':{upstream_version:'1.1.3',advisory:'GHSA-hp3w-g68c-fv3c'},deepmerge:{upstream_version:'4.3.1',advisory:'GHSA-gcqx-w48m-w2h4'},'minimatch-callable':{upstream_version:'11.0.1',advisory:'GHSA-g3hv-75wg-m249'}};
for(const [name,identity] of Object.entries(packages)){
 const directory=path.join(root,'packages/security',name);
 const result=JSON.parse(execFileSync('npm',['pack',directory,'--json','--pack-destination',path.join(root,'onesa-ai-platform-frontend/apps/docs/vendor')],{encoding:'utf8',cwd:root}))[0];
 const source_files={};
 const walk=async dir=>{for(const entry of await fs.readdir(dir,{withFileTypes:true})){if(entry.name==='node_modules')continue;const file=path.join(dir,entry.name);if(entry.isDirectory())await walk(file);else source_files[path.relative(directory,file).split(path.sep).join('/')]=hash(await fs.readFile(file));}};
 await walk(directory);
 const shipped_files=Object.fromEntries(result.files.map(file=>[file.path,source_files[file.path]]));
 const archive='onesa-ai-platform-frontend/apps/docs/vendor/'+result.filename;
 manifest[name]={...identity,archive,archive_sha256:hash(await fs.readFile(path.join(root,archive))),npm_integrity:result.integrity,source_files,shipped_files};
 if(name==='minimatch-callable'){
  const ownerArchive='infra/oracle/vercel-tools/vendor/'+result.filename;
  await fs.mkdir(path.dirname(path.join(root,ownerArchive)),{recursive:true});
  await fs.copyFile(path.join(root,archive),path.join(root,ownerArchive));
  manifest[name].additional_archives=[ownerArchive];
 }
}
await fs.writeFile(path.join(root,'packages/security/provenance.json'),JSON.stringify(manifest,null,2)+'\n');
console.log('Packed reviewed dependency backports and recorded source/archive integrity.');
