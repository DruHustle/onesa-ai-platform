import { csrf } from "./api";
const maximum=5*1024*1024,chunkBytes=512*1024;
function base64(bytes:Uint8Array){let raw="";for(let offset=0;offset<bytes.length;offset+=8192)raw+=String.fromCharCode(...bytes.subarray(offset,offset+8192));return btoa(raw);}
export async function uploadDocument(data:FormData,signal?:AbortSignal):Promise<void>{
  const file=data.get("file");if(!(file instanceof File)||file.size<1||file.size>maximum)throw new Error("Upload a document between 1 byte and 5 MiB");
  const headers={"X-CSRF-Token":csrf(),"Content-Type":"application/json"};
  async function request(path:string,body?:unknown,method="POST",abort=signal){const result=await fetch("/api/v1/knowledge/uploads"+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),credentials:"same-origin",cache:"no-store",signal:abort});if(!result.ok){const error=await result.json().catch(()=>({}));throw new Error(error.error?.message||"Upload failed");}return result.status===204?undefined:result.json();}
  const bytes=new Uint8Array(await file.arrayBuffer());const sha256=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
  let identifier:string|undefined;
  try{
    const result=await request("",{filename:file.name,media_type:file.name.toLowerCase().endsWith(".pdf")?"application/pdf":"text/plain",size:bytes.length,sha256});identifier=result.id;
    for(let offset=0,sequence=0;offset<bytes.length;offset+=chunkBytes,sequence++)await request(`/${identifier}/chunks`,{sequence,base64:base64(bytes.subarray(offset,offset+chunkBytes))});
    await request(`/${identifier}/complete`,{});
  }catch(error){if(identifier)await request(`/${identifier}`,undefined,"DELETE",AbortSignal.timeout(3000)).catch(()=>{});throw error;}
}
