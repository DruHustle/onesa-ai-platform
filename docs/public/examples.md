# Validated API integration examples

Examples derive methods, paths and request bodies from the current OpenAPI. Use an authorized development Origin, a session issued by login and its CSRF cookie. Placeholder IDs must be replaced with owned resource IDs. No SDK is introduced before API stability.

## Authentication

Python requests.Session or a browser same-origin fetch can retain issued cookies. Supply your development email/password via local environment variables; never paste real credentials into documentation. POST /api/v1/auth/login uses email and password; protected mutations require X-CSRF-Token.

```python
import os, requests
base = os.environ["ONESA_APPLICATION_URL"]
session = requests.Session()
session.headers["Origin"] = base
r = session.post(base + "/api/v1/auth/login", json={"email": os.environ["ONESA_DEV_EMAIL"], "password": os.environ["ONESA_DEV_PASSWORD"]})
r.raise_for_status()
session.headers["X-CSRF-Token"] = session.cookies["onesa_csrf"]
```

## GET /api/v1/models

### Python

```python
r = session.get(base + "/api/v1/models")
r.raise_for_status()
print(r.json())
```

### TypeScript

```typescript
const response = await fetch("/api/v1/models", {method: "GET", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfFromSessionCookie}});
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const result = await response.json();
```

### cURL

```bash
curl --request GET "$ONESA_APPLICATION_URL/api/v1/models" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF"
```

## POST /api/v1/conversations

### Python

```python
r = session.post(base + "/api/v1/conversations", json={'title': 'Integration example'})
r.raise_for_status()
print(r.json())
```

### TypeScript

```typescript
const response = await fetch("/api/v1/conversations", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfFromSessionCookie}, body: JSON.stringify({"title": "Integration example"})});
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const result = await response.json();
```

### cURL

```bash
curl --request POST "$ONESA_APPLICATION_URL/api/v1/conversations" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF" --header 'Content-Type: application/json' --data '{"title": "Integration example"}'
```

## POST /api/v1/chat/completions

### Python

```python
r = session.post(base + "/api/v1/chat/completions", json={'conversation_id': '00000000-0000-4000-8000-000000000001', 'content': 'Hello Onesa', 'stream': False})
r.raise_for_status()
print(r.json())
```

### TypeScript

```typescript
const response = await fetch("/api/v1/chat/completions", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfFromSessionCookie}, body: JSON.stringify({"conversation_id": "00000000-0000-4000-8000-000000000001", "content": "Hello Onesa", "stream": false})});
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const result = await response.json();
```

### cURL

```bash
curl --request POST "$ONESA_APPLICATION_URL/api/v1/chat/completions" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF" --header 'Content-Type: application/json' --data '{"conversation_id": "00000000-0000-4000-8000-000000000001", "content": "Hello Onesa", "stream": false}'
```

## POST /api/v1/knowledge/search

### Python

```python
r = session.post(base + "/api/v1/knowledge/search", json={'query': 'inspection interval', 'document_ids': [], 'limit': 5})
r.raise_for_status()
print(r.json())
```

### TypeScript

```typescript
const response = await fetch("/api/v1/knowledge/search", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfFromSessionCookie}, body: JSON.stringify({"query": "inspection interval", "document_ids": [], "limit": 5})});
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const result = await response.json();
```

### cURL

```bash
curl --request POST "$ONESA_APPLICATION_URL/api/v1/knowledge/search" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF" --header 'Content-Type: application/json' --data '{"query": "inspection interval", "document_ids": [], "limit": 5}'
```

## POST /api/v1/agents/runs

### Python

```python
r = session.post(base + "/api/v1/agents/runs", json={'goal': 'Count words in hello platform', 'allowed_tools': ['text_stats']})
r.raise_for_status()
print(r.json())
```

### TypeScript

```typescript
const response = await fetch("/api/v1/agents/runs", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfFromSessionCookie}, body: JSON.stringify({"goal": "Count words in hello platform", "allowed_tools": ["text_stats"]})});
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const result = await response.json();
```

### cURL

```bash
curl --request POST "$ONESA_APPLICATION_URL/api/v1/agents/runs" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF" --header 'Content-Type: application/json' --data '{"goal": "Count words in hello platform", "allowed_tools": ["text_stats"]}'
```

## POST /api/v1/travel/trips

### Python

```python
r = session.post(base + "/api/v1/travel/trips", json={'destination': 'Berlin', 'duration': 2, 'budget': 250, 'currency': 'EUR'})
r.raise_for_status()
print(r.json())
```

### TypeScript

```typescript
const response = await fetch("/api/v1/travel/trips", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfFromSessionCookie}, body: JSON.stringify({"destination": "Berlin", "duration": 2, "budget": 250, "currency": "EUR"})});
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const result = await response.json();
```

### cURL

```bash
curl --request POST "$ONESA_APPLICATION_URL/api/v1/travel/trips" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF" --header 'Content-Type: application/json' --data '{"destination": "Berlin", "duration": 2, "budget": 250, "currency": "EUR"}'
```

## Streaming

Set stream=true and use session.post(..., stream=True). Parse event/data frames using iter_lines(), accumulate content_delta, and require message_end. In TypeScript use Response.body.getReader(), TextDecoder with stream=true, and buffer complete SSE frames across chunks. AbortController cancels the request. Never treat a transport chunk as an entire event. See [streaming contract](streaming.md).

### Runnable Python stream

Use the authenticated session from the previous example and replace conversation_id with your owned conversation. The context manager closes the stream on error or cancellation.

```python
import json
finished = False
with session.post(base + '/api/v1/chat/completions', json={'conversation_id': conversation_id, 'content': 'Hello', 'stream': True}, stream=True) as response:
    response.raise_for_status()
    kind = ''
    for line in response.iter_lines(decode_unicode=True):
        if line.startswith('event: '):
            kind = line[7:]
        elif line.startswith('data: '):
            data = json.loads(line[6:])
            if kind == 'content_delta':
                print(data['text'], end='', flush=True)
            elif kind == 'error':
                raise RuntimeError('Generation failed; inspect the controlled error code')
            elif kind == 'message_end':
                finished = True
    if not finished:
        raise RuntimeError('Incomplete stream')
```

### Runnable browser TypeScript stream

Run on the application origin with an authenticated session. Pass your owned conversationId and the session CSRF value. AbortController.signal closes the request when the caller cancels.

```typescript
async function streamChat(conversationId: string, csrf: string, signal: AbortSignal) {
  const response = await fetch('/api/v1/chat/completions', {method:'POST', credentials:'same-origin', signal, headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify({conversation_id:conversationId,content:'Hello',stream:true})});
  if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
  const reader=response.body.getReader(); const decoder=new TextDecoder();
  let buffer='', finished=false;
  try {
    while (true) {
      const {value,done}=await reader.read();
      buffer += decoder.decode(value,{stream:!done});
      let boundary: number;
      while ((boundary=buffer.indexOf('\n\n')) >= 0) {
        const frame=buffer.slice(0,boundary); buffer=buffer.slice(boundary+2);
        const lines=frame.split('\n');
        const kind=lines.find(line=>line.startsWith('event: '))?.slice(7);
        const payload=lines.filter(line=>line.startsWith('data: ')).map(line=>line.slice(6)).join('\n');
        if (!payload) continue;
        const data=JSON.parse(payload);
        if (kind==='content_delta') console.log(data.text);
        if (kind==='error') throw new Error('Generation failed');
        if (kind==='message_end') finished=true;
      }
      if (done) break;
    }
    if (!finished) throw new Error('Incomplete stream');
  } finally { await reader.cancel(); reader.releaseLock(); }
}
```

### cURL stream

```bash
curl --no-buffer "$ONESA_APPLICATION_URL/api/v1/chat/completions" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF" --header 'Content-Type: application/json' --data '{"conversation_id":"00000000-0000-4000-8000-000000000001","content":"Hello","stream":true}'
```
