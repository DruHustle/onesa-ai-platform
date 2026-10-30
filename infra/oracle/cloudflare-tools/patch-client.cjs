// Apply exactly two reviewed changes to the lockfile-pinned official client.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=process.argv[2];assert.ok(path.isAbsolute(root));
const file=path.join(root,'node_modules/wrangler/wrangler-dist/cli.js'),raw=fs.readFileSync(file);
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
assert.equal(hash(raw),'18dbf242b542e171c993d68cc41a4e58bc4f533392fc91b71e29ffeee7bf6c0c');
const original=raw.toString('utf8');let changed=original;
for(const [before,after] of [
 ['if (e11.code === 8e6 /* UNKNOWN_ERROR */ && attempts < MAX_DEPLOYMENT_ATTEMPTS) {','if (false && e11.code === 8e6 /* UNKNOWN_ERROR */ && attempts < MAX_DEPLOYMENT_ATTEMPTS) {'],
 ['method: "POST",\n          body: formData','method: "POST",\n          redirect: "error",\n          body: formData'],
]){assert.equal(changed.split(before).length,2);changed=changed.replace(before,after);}
assert.equal(hash(Buffer.from(changed)),'95783b16eadfa64161f0fd7c453f3c424a21c855c9afc445ea4a5703c6b512fe');
fs.writeFileSync(file,changed);
