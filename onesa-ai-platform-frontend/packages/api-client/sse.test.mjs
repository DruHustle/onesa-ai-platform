import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chatEvents} from './sse.ts';
const encoder=new TextEncoder();
const start='event: message_start\r\ndata: {"conversation_id":"c","run_id":"r"}\r\n\r\n';
const end='event: message_end\r\ndata: {"message_id":"m","model":{"backend":"mock","model_identifier":"fixture","real_inference":false}}\r\n\r\n';
function stream(text, step=1){const bytes=encoder.encode(text);let offset=0;return new ReadableStream({pull(controller){if(offset===bytes.length){controller.close();return;}controller.enqueue(bytes.slice(offset,offset+step));offset=Math.min(bytes.length,offset+step);}});}
async function collect(text,step){const out=[];for await(const event of chatEvents(stream(text,step)))out.push(event);return out;}
test('UTF-8 and CRLF boundaries, multiline data and terminal event',async()=>{const out=await collect(start+'event: content_delta\r\ndata: {\r\ndata: "text":"Grüße 🌍"}\r\n\r\n'+end);assert.equal(out[1].text,'Grüße 🌍');assert.equal(out[2].kind,'message_end');});
test('truncated response fails',async()=>{await assert.rejects(collect(start),/interrupted/);});
test('invalid delta is rejected at runtime',async()=>{await assert.rejects(collect(start+'event: content_delta\ndata: {"text":7}\n\n'+end),/Invalid stream delta/);});
test('frame size and total text have hard limits',async()=>{await assert.rejects(collect('x'.repeat(1048577),1048577),/frame exceeds/);await assert.rejects(collect(start+'event: content_delta\ndata: '+JSON.stringify({text:'x'.repeat(128001)})+'\n\n'+end,200000),/text exceeds/);});
test('terminal error and duplicate completion',async()=>{const error='event: error\ndata: {"code":"MODEL","message":"Unavailable","request_id":"r"}\n\n';assert.equal((await collect(error))[0].kind,'error');await assert.rejects(collect(start+end+end),/after terminal/);});
