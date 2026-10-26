// AI-owned binary backup extension. Existing database v1 archives stay unchanged.
import crypto from 'node:crypto';
export const MAX_FILE=4*1024*1024;
export const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const need=v=>{if(!v)throw Error('Invalid AI file backup');};
export function sealFile(bytes,publicKey){
 need(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=MAX_FILE);
 const pub=crypto.createPublicKey(publicKey);
 need(pub.asymmetricKeyType==='rsa'&&pub.asymmetricKeyDetails.modulusLength>=2048);
 const meta={format:'onesa-ai-twin-file-v1',key_id:sha(publicKey),sha256:sha(bytes),size:bytes.length};
 const key=crypto.randomBytes(32),nonce=crypto.randomBytes(12);
 try{
  const cipher=crypto.createCipheriv('aes-256-gcm',key,nonce);cipher.setAAD(Buffer.from(JSON.stringify(meta)));
  const body=Buffer.concat([cipher.update(bytes),cipher.final()]);
  return {meta,wrapped_key:crypto.publicEncrypt({key:pub,oaepHash:'sha256',padding:crypto.constants.RSA_PKCS1_OAEP_PADDING},key).toString('base64'),nonce:nonce.toString('base64'),body:body.toString('base64'),tag:cipher.getAuthTag().toString('base64')};
 }finally{key.fill(0);}
}
export function openFile(body,privateKey,expected){
 need(Buffer.isBuffer(body)&&body.length<MAX_FILE*2&&sha(body)===expected.ciphertext_sha256);
 const e=JSON.parse(body),m=e.meta,pub=crypto.createPublicKey(crypto.createPrivateKey(privateKey)).export({type:'spki',format:'pem'});
 need(m?.format==='onesa-ai-twin-file-v1'&&m.key_id===sha(pub)&&m.sha256===expected.sha256&&m.size===expected.size&&m.size>0&&m.size<=MAX_FILE);
 const key=crypto.privateDecrypt({key:privateKey,oaepHash:'sha256',padding:crypto.constants.RSA_PKCS1_OAEP_PADDING},Buffer.from(e.wrapped_key,'base64'));
 try{
  const nonce=Buffer.from(e.nonce,'base64'),tag=Buffer.from(e.tag,'base64');need(key.length===32&&nonce.length===12&&tag.length===16);
  const d=crypto.createDecipheriv('aes-256-gcm',key,nonce);d.setAAD(Buffer.from(JSON.stringify(m)));d.setAuthTag(tag);
  const bytes=Buffer.concat([d.update(Buffer.from(e.body,'base64')),d.final()]);need(bytes.length===m.size&&sha(bytes)===m.sha256);return bytes;
 }finally{key.fill(0);}
}
