import type { Operations } from "./contracts";
export type * from "./contracts";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly code: string) {
    super(message);
    this.name = "ApiError";
  }
}

export const csrf = () =>
  document.cookie.split("; ").find((v) => v.startsWith("onesa_csrf="))
    ?.split("=").slice(1).join("=") || "";

export async function call(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<Response> {
  if (!path.startsWith("/") || path.startsWith("//")) throw new Error("Invalid API path");
  const response = await fetch(`/api/v1${path}`, {
    method, signal, credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/") && path !== "/documentation/access" && typeof window !== "undefined") window.dispatchEvent(new Event("onesa-session-expired"));
    const data = await response.json().catch(() => ({}));
    throw new ApiError(data.error?.message || "Request failed", response.status, data.error?.code || "request_failed");
  }
  return response;
}

// Route templates provide request/response inference, including dynamic ownership-scoped routes.
export async function api<K extends keyof Operations>(operation: K, options?: {
  body?: Operations[K]["body"];
  params?: Record<string, string>;
  query?: Record<string, string | number | undefined>;
  signal?: AbortSignal;
}): Promise<Operations[K]["response"]> {
  const [method, template] = operation.split(" ");
  const path = template.replace(/\{([^}]+)\}/g, (_, name) => {
    const value = options?.params?.[name];
    if (!value) throw new Error(`Missing route parameter: ${name}`);
    return encodeURIComponent(value);
  });
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(options?.query || {})) if (value !== undefined) query.set(name, String(value));
  const response = await call(path + (query.size ? `?${query}` : ""), method, options?.body, options?.signal);
  return response.status === 204 ? undefined : response.json();
}
