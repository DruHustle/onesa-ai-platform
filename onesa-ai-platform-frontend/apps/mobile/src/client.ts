import type { z } from 'zod';
import { apiURL, NATIVE_ORIGIN, type Credential } from './protocol.ts';

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}
export type Fetch = (url: string, init: RequestInit) => Promise<Response>;

export class Client {
  private credential: Credential | null = null;
  private generation = 0;
  private requests = new Set<AbortController>();
  private readonly transport: Fetch;
  readonly expired: () => void;
  constructor(transport: Fetch, expired: () => void) { this.transport = transport; this.expired = expired; }
  setCredential(credential: Credential | null) {
    this.generation++;
    for (const request of this.requests) request.abort();
    this.requests.clear();
    this.credential = credential;
  }
  async request(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<Response> {
    const url = apiURL(path), generation = this.generation;
    const publicRoute = path === '/auth/native/start' || path === '/auth/native/token';
    if (!publicRoute && (!this.credential || Date.parse(this.credential.expires_at) <= Date.now())) {
      this.expired(); throw new ApiError(401, 'Sign in to continue.');
    }
    const controller = new AbortController();
    this.requests.add(controller);
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
    const generationRequest = method === 'POST' && ['/chat/completions', '/agents/runs', '/travel/trips'].includes(path);
    const timer = setTimeout(abort, generationRequest ? 150000 : 30000);
    const cleanup = () => { clearTimeout(timer); this.requests.delete(controller); signal?.removeEventListener('abort', abort); };
    let bodyOwnsCleanup = false;
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json', 'Origin': NATIVE_ORIGIN, 'Accept': path === '/chat/completions' ? 'text/event-stream' : 'application/json' };
      if (!publicRoute) headers.Authorization = `Bearer ${this.credential!.access_token}`;
      const response = await this.transport(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal, credentials: 'omit', redirect: 'error', cache: 'no-store' });
      if (generation !== this.generation) { await response.body?.cancel(); throw new Error('Account changed; response discarded.'); }
      if (!response.ok) {
        if ([401, 403].includes(response.status) && !publicRoute) this.expired();
        // Do not display server/proxy bodies that may contain private debug output.
        const message = response.status === 401 ? 'Your session has expired. Sign in again.' : response.status === 403 ? 'Your account cannot perform this action.' : response.status === 404 && publicRoute ? 'Native sign-in is not available on this service yet.' : response.status === 409 ? 'This task is already running or changed. Refresh before trying again.' : response.status === 429 ? 'Too many requests. Please wait before trying again.' : 'The service could not complete the request. Your input is preserved.';
        await response.body?.cancel();
        throw new ApiError(response.status, message);
      }
      if (!response.body) { cleanup(); return response; }
      const reader = response.body.getReader();
      let completed = false, bytes = 0;
      let downstream: ReadableStreamDefaultController<Uint8Array> | null = null;
      const finish = () => { completed = true; cleanup(); controller.signal.removeEventListener('abort', abortBody); };
      const abortBody = () => {
        if (completed) return;
        finish(); void reader.cancel().catch(() => {});
        downstream?.error(new Error('Request cancelled.'));
      };
      controller.signal.addEventListener('abort', abortBody, { once: true });
      const guarded = new ReadableStream<Uint8Array>({
        start(stream) { downstream = stream; },
        pull: async stream => {
          if (completed) return;
          try {
            const part = await reader.read();
            if (completed) return;
            if (generation !== this.generation || controller.signal.aborted) throw new Error('Account changed; response discarded.');
            if (part.done) { finish(); stream.close(); return; }
            bytes += part.value.byteLength;
            if (bytes > 2 * 1024 * 1024) throw new Error('Service response exceeded the supported size.');
            stream.enqueue(part.value);
          } catch (error) { if (!completed) { finish(); void reader.cancel().catch(() => {}); stream.error(error); } }
        },
        cancel: async () => { if (!completed) { finish(); await reader.cancel().catch(() => {}); } },
      });
      bodyOwnsCleanup = true;
      if (controller.signal.aborted) abortBody();
      return new Response(guarded, { status: response.status, statusText: response.statusText, headers: response.headers });
    } finally {
      if (!bodyOwnsCleanup) cleanup();
    }
  }
  async json<T>(schema: z.ZodType<T>, path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
    const generation = this.generation;
    const response = await this.request(path, method, body, signal);
    const text = await response.text();
    if (generation !== this.generation) throw new Error('Account changed; response discarded.');
    if (text.length > 2 * 1024 * 1024) throw new Error('Service response exceeded the supported size.');
    return schema.parse(JSON.parse(text));
  }
}
