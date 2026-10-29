// Bound this disposable browser process and its descendants; never retry a failed check.
import {runOwnedBrowserCheck} from './owned-browser-check.mjs';
const result=await runOwnedBrowserCheck(new URL('./visual-acceptance-worker.mjs',import.meta.url),{timeoutMs:480000});
if(result.timedOut)console.error('DOCS_VISUAL_ACCEPTANCE_DEADLINE_FAILED_NOT_QUALIFIED');
process.exitCode=result.code;
