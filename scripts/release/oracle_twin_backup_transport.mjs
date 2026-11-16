// Existing private AI backup prefix/bucket/key/cap; no deletion or overwrite.
import fs from 'node:fs';
import {S3Client,GetObjectCommand,PutObjectCommand,ListObjectsV2Command} from '@aws-sdk/client-s3';
import {sealFile,sha,MAX_FILE} from './oracle_twin_backup_crypto.mjs';
const need=v=>{if(!v)throw Error('AI backup transport refused');};
const MAX=64*1024*1024,prefix='.onesa-database-backups/v1/ai/';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const config=JSON.parse(fs.readFileSync('/private/transport.json'));
need(sha(Buffer.from(process.env.S3_ENDPOINT))===config.endpoint_sha256&&sha(Buffer.from(process.env.S3_BUCKET))===config.bucket_sha256);
const client=new S3Client({endpoint:process.env.S3_ENDPOINT,region:process.env.S3_REGION,forcePathStyle:true}),Bucket=process.env.S3_BUCKET;
function durable(name,value){const p='/private/receipts/'+name;const fd=fs.openSync(p,'wx',0o600);try{fs.writeFileSync(fd,JSON.stringify(value));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}const parent=fs.openSync('/private/receipts','r');try{fs.fsyncSync(parent);}finally{fs.closeSync(parent);}}
async function get(Key){const r=await client.send(new GetObjectCommand({Bucket,Key}));need(Number(r.ContentLength)<=MAX_FILE*2);return Buffer.from(await r.Body.transformToByteArray());}
const keyFor=(keyId,hash)=>{need(/^[a-f0-9]{64}$/.test(keyId)&&/^[a-f0-9]{64}$/.test(hash));return prefix+'files/'+keyId+'-'+hash+'.json';};
try{
 need(['put','inspect'].includes(input.action)&&Array.isArray(input.files)&&input.files.length<=1000);
 const publicKey=fs.readFileSync('/recovery/public.pem'),keyId=sha(publicKey);
 let total=0,token,pages=0;
 do{const r=await client.send(new ListObjectsV2Command({Bucket,Prefix:prefix,ContinuationToken:token}));for(const f of r.Contents||[])total+=Number(f.Size);token=r.NextContinuationToken;need(++pages<=10);}while(token);
 need(total<=MAX);const receipts=[];
 for(const file of input.files){
  const Key=keyFor(keyId,file.sha256);need(Number.isSafeInteger(file.size)&&file.size>0&&file.size<=MAX_FILE);
  if(file.prior){
   need(file.prior.object_key===Key&&file.prior.key_id===keyId&&file.prior.sha256===file.sha256&&file.prior.size===file.size);
   const body=await get(Key);need(sha(body)===file.prior.ciphertext_sha256);receipts.push(file.prior);continue;
  }
  need(input.action==='put'&&/^[a-f0-9]{64}$/.test(file.sha256));
  const bytes=fs.readFileSync('/private/files/'+file.sha256);need(bytes.length===file.size&&sha(bytes)===file.sha256);
  const body=Buffer.from(JSON.stringify(sealFile(bytes,publicKey)));need(total+body.length<=MAX);
  const receipt={object_key:Key,key_id:keyId,sha256:file.sha256,size:file.size,ciphertext_sha256:sha(body)};
  durable(file.sha256+'.intent.json',receipt);
  // If an earlier interrupted request created this key, do not replace it or
  // silently accept its unregistered ciphertext. Reconcile the retained intent.
  await client.send(new PutObjectCommand({Bucket,Key,Body:body,IfNoneMatch:'*',ServerSideEncryption:'AES256',ContentType:'application/json'}));
  need(sha(await get(Key))===sha(body));total+=body.length;
  durable(file.sha256+'.verified.json',receipt);receipts.push(receipt);
 }
 console.log(JSON.stringify({status:'PASS',files:receipts,prefix_bytes:total,cap_bytes:MAX,automatic_deletion:false}));
}catch{console.error('AI encrypted backup transport refused; inspect retained intent; no secrets logged');process.exitCode=1;}
