// Build-only official npm code; runtime dependencies come from the separate lock.
const fs = require('node:fs');
const https = require('node:https');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');
const meta = JSON.parse(fs.readFileSync('/opt/npm-runtime/upstream.json'));
if (meta.version !== '12.2.1' || meta.url !== 'https://registry.npmjs.org/npm/-/npm-12.2.1.tgz' || !/^sha512-[A-Za-z0-9+/=]+$/.test(meta.integrity)) throw Error('npm source profile');
https.get(meta.url, response => {
  if (response.statusCode !== 200) throw Error('npm source response');
  let size = 0; const chunks = [];
  response.on('data', b => { size += b.length; if (size > 16 * 1024 * 1024) response.destroy(Error('npm source bound')); else chunks.push(b); });
  response.on('end', () => {
    const body = Buffer.concat(chunks);
    if ('sha512-' + crypto.createHash('sha512').update(body).digest('base64') !== meta.integrity) throw Error('npm source identity');
    fs.writeFileSync('/tmp/npm-code.tgz', body, {flag:'wx',mode:0o600});
    fs.mkdirSync('/opt/onesa-npm-code');
    const result = spawnSync('tar',['-xzf','/tmp/npm-code.tgz','--strip-components=1','--exclude=package/node_modules','-C','/opt/onesa-npm-code']);
    if (result.status !== 0) throw Error('npm source extraction');
    fs.symlinkSync('/opt/npm-runtime/node_modules','/opt/onesa-npm-code/node_modules');
    fs.unlinkSync('/tmp/npm-code.tgz');
  });
}).on('error', () => {process.exitCode = 1;});
