import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {sealFile,openFile,sha} from './oracle_twin_backup_crypto.mjs';
const pair=crypto.generateKeyPairSync('rsa',{modulusLength:2048,publicKeyEncoding:{type:'spki',format:'pem'},privateKeyEncoding:{type:'pkcs8',format:'pem'}});
test('owned binary encryption roundtrip and source binding',()=>{
 const bytes=Buffer.from('Synthetic isolated pump model'),sealed=sealFile(bytes,Buffer.from(pair.publicKey)),body=Buffer.from(JSON.stringify(sealed));
 const expected={sha256:sha(bytes),size:bytes.length,ciphertext_sha256:sha(body)};
 assert.deepEqual(openFile(body,pair.privateKey,expected),bytes);
 for(const field of ['sha256','size','ciphertext_sha256'])assert.throws(()=>openFile(body,pair.privateKey,{...expected,[field]:field==='size'?1:'0'.repeat(64)}));
 const modified=Buffer.from(JSON.stringify({...sealed,meta:{...sealed.meta,size:1}}));assert.throws(()=>openFile(modified,pair.privateKey,{...expected,ciphertext_sha256:sha(modified),size:1}));
 const forged=Buffer.from(JSON.stringify({...sealed,body:Buffer.from('forged').toString('base64')}));assert.throws(()=>openFile(forged,pair.privateKey,{...expected,ciphertext_sha256:sha(forged)}));
});
test('file and recovery key bounds fail closed',()=>{
 assert.throws(()=>sealFile(Buffer.alloc(0),Buffer.from(pair.publicKey)));assert.throws(()=>sealFile(Buffer.alloc(4194305),Buffer.from(pair.publicKey)));
 const ed=crypto.generateKeyPairSync('ed25519',{publicKeyEncoding:{type:'spki',format:'pem'}});assert.throws(()=>sealFile(Buffer.from('x'),Buffer.from(ed.publicKey)));
});
