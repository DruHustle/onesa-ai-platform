import {spawn} from 'node:child_process';
if(process.env.ONESA_DOCS_SCOPE==='internal')throw new Error('Internal development must use the protected gateway; static/dev serving is forbidden.');
const child=spawn(process.execPath,['node_modules/@docusaurus/core/bin/docusaurus.mjs','start','--host','127.0.0.1','--port','3200'],{stdio:'inherit',env:{...process.env,ONESA_DOCS_SCOPE:'public'}});
child.on('exit',code=>process.exit(code||0));
