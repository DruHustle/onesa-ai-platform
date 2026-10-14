// Server-only same-origin BFF. The destination is operator configuration, never browser input.
import "server-only";

export async function proxy(request: Request): Promise<Response> {
  const incoming = new URL(request.url);
  if (!incoming.pathname.startsWith("/api/v1/") &&
      incoming.pathname !== "/health" && incoming.pathname !== "/ready") {
    return new Response(null, { status: 404 });
  }
  try {
    const base = new URL(process.env.ONESA_API_URL || "http://127.0.0.1:8000");
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password ||
        base.pathname !== '/' || base.search || base.hash) {
      throw new Error("Invalid server API origin");
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
      .filter(cookie => ['onesa_session', 'onesa_csrf'].includes(cookie.split('=', 1)[0]));
    if (applicationCookies.length) headers.set('cookie', applicationCookies.join('; '));
    else headers.delete('cookie');
    // Avoid transparent fetch decompression leaving incorrect response headers.
    headers.set('accept-encoding', 'identity');
    const timeout = Number(process.env.ONESA_PROXY_TIMEOUT_SECONDS || "135");
    if (!Number.isFinite(timeout) || timeout < 1 || timeout > 600) {
      throw new Error("Invalid proxy timeout");
    }
    // The backend authenticates this route only with its fixed, nonempty session cookie.
    // This negative result avoids waking a sleeping API for signed-out startup; it is not readiness.
    const hasSession = applicationCookies.some(cookie =>
      cookie.startsWith('onesa_session=') && cookie.slice('onesa_session='.length) !== '');
    if (request.method === 'GET' && incoming.pathname === '/api/v1/auth/me' && !hasSession) {
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
      const redirect = new URL(location, base);
      if (redirect.host !== base.host || !["http:", "https:"].includes(redirect.protocol)) throw new Error("Invalid upstream redirect");
      responseHeaders.set('location', redirect.pathname + redirect.search + redirect.hash);
    }
    responseHeaders.delete('set-cookie');
    for (const cookie of upstream.headers.getSetCookie()) responseHeaders.append('set-cookie', cookie);
    responseHeaders.set('cache-control', 'no-store');
    // Forward the stream directly: response-body cancellation closes the upstream stream.
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json({ error: { code: 'backend_unavailable', message: 'Service temporarily unavailable' } }, { status: 503 });
  }
}
