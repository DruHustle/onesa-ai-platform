// Supervise only the isolated fixture browser's own process group.
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export async function runOwnedBrowserCheck(script,{timeoutMs=480000}={}){
 if(!Number.isSafeInteger(timeoutMs)||timeoutMs<50||timeoutMs>480000)throw new Error('Invalid browser fixture deadline');
 if(process.platform==='win32')throw new Error('Owned browser process groups require the supported POSIX runner');
 const child=spawn(process.execPath,[fileURLToPath(script)],{detached:true,stdio:'inherit'});
 let timedOut=false,interrupted=false;
 function stop(){
  if(!child.pid)return;
  try{process.kill(-child.pid,'SIGKILL');}catch(error){if(error.code!=='ESRCH')throw error;}
 }
 const timer=setTimeout(()=>{timedOut=true;stop();},timeoutMs);
 const interrupt=()=>{interrupted=true;stop();};
 process.once('SIGINT',interrupt);process.once('SIGTERM',interrupt);
 try{
  return await new Promise(resolve=>{
   child.once('error',()=>resolve({code:1,timedOut:false}));
   child.once('exit',(code)=>resolve({code:interrupted?130:timedOut?1:code===0?0:1,timedOut}));
  });
 }finally{
  clearTimeout(timer);process.off('SIGINT',interrupt);process.off('SIGTERM',interrupt);
  stop(); // A failed worker must not leave its own detached browser descendants.
 }
}
