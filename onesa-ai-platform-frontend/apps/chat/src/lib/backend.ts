import "./server/tls-trust";
// Server-only same-origin BFF; the destination is operator configuration.
import "server-only";

const nativeOrigin = "onesaai://native";
const nativeUUID = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const nativeRoutes: [string, string][] = [
  ["GET", "/api/v1/auth/me"],
  ["POST", "/api/v1/auth/native/(?:start|token|logout)"],
  ["GET", "/api/v1/models(?:/[A-Za-z0-9_.-]{1,80})?"],
  ["GET|POST", "/api/v1/conversations"],
  ["GET|PATCH|DELETE", `/api/v1/conversations/${nativeUUID}`],
  ["POST", `/api/v1/conversations/${nativeUUID}/cancel`],
  ["POST", "/api/v1/chat/completions"],
  ["GET|POST", "/api/v1/knowledge/documents"],
  ["GET|DELETE", `/api/v1/knowledge/documents/${nativeUUID}`],
  ["POST", `/api/v1/knowledge/documents/${nativeUUID}/reindex`],
  ["POST", "/api/v1/knowledge/search"],
  ["GET", "/api/v1/agents/tools"],
  ["GET|POST", "/api/v1/agents/runs"],
  ["GET", `/api/v1/agents/runs/${nativeUUID}`],
  ["POST", `/api/v1/agents/runs/${nativeUUID}/cancel`],
  ["GET|POST", "/api/v1/travel/trips"],
  ["GET|PUT|DELETE", `/api/v1/travel/trips/${nativeUUID}`],
];

export async function proxy(request: Request): Promise<Response> {
  const incoming = new URL(request.url);
  if (!incoming.pathname.startsWith("/api/v1/") &&
      incoming.pathname !== "/health" && incoming.pathname !== "/ready") {
    return new Response(null, { status: 404 });
  }
  const native = request.headers.get("origin") === nativeOrigin ||
    (request.headers.get("authorization") || "").startsWith("Bearer nai_");
  if (native && (request.headers.get("origin") !== nativeOrigin ||
      request.headers.has("cookie") || request.headers.has("x-csrf-token") ||
      ![null, "none"].includes(request.headers.get("sec-fetch-site")) ||
      !nativeRoutes.some(([methods, path]) => methods.split("|").includes(request.method) &&
        new RegExp(`^${path}$`).test(incoming.pathname)))) {
    return Response.json({ error: { code: "native_route_rejected", message: "Use the native sign-in session for an allowed app route" } },
      { status: 403, headers: { "cache-control": "no-store" } });
  }
  try {
    const base = new URL(process.env.ONESA_API_URL || "http://127.0.0.1:8000");
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password ||
        base.pathname !== '/' || base.search || base.hash) {
      throw new Error("Invalid server API origin");
    }
    const loopback = (host: string) => ["localhost", "127.0.0.1", "[::1]"].includes(host);
    // The default local Compose frontend reaches its API by the internal service name.
    const localUpstream = loopback(base.hostname) || base.origin === "http://api:8000";
    // Next standalone can use its internal listener in Request.url. Only a configured
    // loopback Compose origin with the exact incoming Host can identify a local browser.
    const publicOrigin = process.env.ONESA_PUBLIC_ORIGIN ? new URL(process.env.ONESA_PUBLIC_ORIGIN) : null;
    const localComposeRequest = base.origin === "http://api:8000" && publicOrigin &&
      loopback(publicOrigin.hostname) && request.headers.get("host") === publicOrigin.host;
    const hosted = process.env.VERCEL || (publicOrigin && !loopback(publicOrigin.hostname)) ||
      (!loopback(incoming.hostname) && !localComposeRequest) || !localUpstream;
    const passwordEndpoint = /^\/api\/v1\/auth\/(login|register|recovery\/(request|complete))\/?$/;
    if (hosted && request.method === "POST" && passwordEndpoint.test(incoming.pathname)) {
      return Response.json({ error: { code: "shared_sign_in_required", message: "Continue with your Onesa account" } },
        { status: 403, headers: { "cache-control": "no-store" } });
    }
    const headers = new Headers(request.headers);
    for (const name of ['host', 'connection', 'transfer-encoding', 'content-length',
                        'forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto',
                        'x-vercel-protection-bypass', 'x-vercel-set-bypass-cookie']) {
      headers.delete(name);
    }
    for (const name of Array.from(headers.keys())) {
      if (name.startsWith('x-vercel-')) headers.delete(name);
    }
    // Provider login/bypass cookies belong to Vercel, never the upstream API.
    const applicationCookies = (headers.get('cookie') || '').split(';')
      .map(cookie => cookie.trim())
      .filter(cookie => ['onesa_session', 'onesa_csrf', 'onesa_identity_flow'].includes(cookie.split('=', 1)[0]));
    if (applicationCookies.length) headers.set('cookie', applicationCookies.join('; '));
    else headers.delete('cookie');
    // Avoid transparent fetch decompression leaving incorrect response headers.
    headers.set('accept-encoding', 'identity');
    const timeout = Number(process.env.ONESA_PROXY_TIMEOUT_SECONDS || "135");
    if (!Number.isFinite(timeout) || timeout < 1 || timeout > 600) {
      throw new Error("Invalid proxy timeout");
    }
    // Cookie requests use the fixed session cookie; native requests must reach
    // the backend for independent bearer, owner and issuer validation.
    // This negative result avoids waking a sleeping API for signed-out startup; it is not readiness.
    const hasSession = applicationCookies.some(cookie =>
      cookie.startsWith('onesa_session=') && cookie.slice('onesa_session='.length) !== '');
    if (!native && request.method === 'GET' && incoming.pathname === '/api/v1/auth/me' && !hasSession) {
      const requestId = crypto.randomUUID();
      return Response.json({error: {code: 'unauthorized', message: 'Sign in to continue', request_id: requestId}}, {
        status: 401,
        headers: {'cache-control': 'no-store', 'x-content-type-options': 'nosniff', 'x-request-id': requestId},
      });
    }
    const upstream = await fetch(new URL(incoming.pathname + incoming.search, base), {
      method: request.method,
      headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(timeout * 1000)]),
      redirect: 'manual',
      cache: 'no-store',
      // Node requires duplex for a streaming request body (including file uploads).
      ...({ duplex: 'half' } as Record<string, string>),
    });
    const responseHeaders = new Headers(upstream.headers);
    for (const name of ['connection', 'transfer-encoding', 'content-length', 'content-encoding']) {
      responseHeaders.delete(name);
    }
    const location = responseHeaders.get('location');
    if (location) {
      if (native) throw new Error("Native API redirects are not allowed");
      const redirect = new URL(location, base);
      const mobileCallback = incoming.pathname === '/api/v1/auth/onesa/callback' &&
        request.method === 'GET' && upstream.status === 303 &&
        redirect.protocol === 'onesaai:' && redirect.host === 'account' && redirect.pathname === '/callback' &&
        !redirect.username && !redirect.password && !redirect.hash &&
        redirect.searchParams.getAll('state').length === 1 && /^native_[a-zA-Z0-9_-]{43}$/.test(redirect.searchParams.get('state') || '');
      if (!mobileCallback && (redirect.host !== base.host || !["http:", "https:"].includes(redirect.protocol))) throw new Error("Invalid upstream redirect");
      if (!mobileCallback) responseHeaders.set('location', redirect.pathname + redirect.search + redirect.hash);
    }
    responseHeaders.delete('set-cookie');
    if (!native) {
      const allowedResponseCookies = new Set([
        'onesa_session',
        'onesa_csrf',
        'onesa_identity_flow',
      ]);
      for (const cookie of upstream.headers.getSetCookie()) {
        const pair = cookie.split(';', 1)[0];
        const separator = pair.indexOf('=');
        const name = separator > 0 ? pair.slice(0, separator).trim() : '';
        if (allowedResponseCookies.has(name)) responseHeaders.append('set-cookie', cookie);
      }
    }
    responseHeaders.set('cache-control', 'no-store');
    // Forward the stream directly: response-body cancellation closes the upstream stream.
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json(
      { error: { code: 'backend_unavailable', message: 'Service temporarily unavailable' } },
      { status: 503, headers: { 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' } },
    );
  }
}
