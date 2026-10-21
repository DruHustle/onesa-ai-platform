import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export async function secureInternalOutput(directory) {
 if(path.basename(directory)!=='build-internal')throw new Error('Fixed internal build directory required');
 const root=await fs.lstat(directory);if(!root.isDirectory()||root.isSymbolicLink())throw new Error('Regular internal build directory required');
 let files=0,directories=0;
 async function visit(current){
  const stat=await fs.lstat(current);if(stat.isSymbolicLink())throw new Error('Internal build symlink refused');
  if(stat.isDirectory()){await fs.chmod(current,0o700);directories++;for(const name of await fs.readdir(current))await visit(path.join(current,name));}
  else if(stat.isFile()){await fs.chmod(current,0o600);files++;}
  else throw new Error('Unsupported internal build entry');
 }
 await visit(directory);return {scope:'internal',files,directories,permissions:'directories700/files600'};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const directory=fileURLToPath(new URL('../../onesa-ai-platform-frontend/apps/docs/build-internal/',import.meta.url));
 console.log(JSON.stringify(await secureInternalOutput(directory)));
}
