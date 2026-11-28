"use client";

import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { ApiError, call } from "../../../lib/api";
import OnesaSignIn, { IdentityEntryStatus, useOnesaIdentity } from "../../../components/onesa-sign-in";

const userSchema = z.object({ id: z.string().uuid(), email: z.string().email(), display_name: z.string() });
const requestSchema = z.object({
  request_id: z.string().uuid(), app_name: z.literal("Onesa AI Platform"),
  platform: z.enum(["ios", "android"]), expires_at: z.string().datetime({ offset: true }),
  status: z.enum(["pending", "approved", "consumed"]), user: userSchema,
});

function appReturn(value: unknown): string {
  const { redirect_url } = z.object({ redirect_url: z.string().max(1000) }).parse(value);
  const url = new URL(redirect_url);
  if (url.protocol !== "onesaai:" || url.hostname !== "auth" || url.pathname !== "/callback" || url.port || url.username || url.password || url.hash ||
      [...url.searchParams.keys()].some(key => key !== "state" && key !== "code") ||
      ["code", "state"].some(key => url.searchParams.getAll(key).length !== 1 || !/^[A-Za-z0-9_-]{43,128}$/.test(url.searchParams.get(key) || ""))) throw new Error("Invalid native return destination");
  return url.href;
}

export default function NativeConsent() {
  const method = useOnesaIdentity(), [requestId, setRequestId] = useState("");
  const [details, setDetails] = useState<z.infer<typeof requestSchema> | null>(null), [signedOut, setSignedOut] = useState(false);
  const [busy, setBusy] = useState(true), [error, setError] = useState(""), [returnURL, setReturnURL] = useState("");
  const [attempted, setAttempted] = useState(false);
  const submitting = useRef(false);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search), id = query.get("request") || "";
    if (query.getAll("request").length !== 1 || !z.string().uuid().safeParse(id).success) {
      Promise.resolve().then(() => { setError("Open sign-in from the installed Onesa AI Platform app."); setBusy(false); }); return;
    }
    const controller = new AbortController();
    void call(`/auth/native/requests/${id}`, "GET", undefined, AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]))
      .then(response => response.json()).then(value => {
        const next = requestSchema.parse(value);
        if (next.request_id !== id || Date.parse(next.expires_at) <= Date.now()) throw new Error("Expired request");
        if (!controller.signal.aborted) { setRequestId(id); setDetails(next); }
      }).catch(reason => {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.status === 401) { setRequestId(id); setSignedOut(true); }
        else setError("This sign-in request is unavailable or expired. Return to the app and start again.");
      }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, []);

  async function approve() {
    if (submitting.current || !details || details.status !== "pending" || Date.parse(details.expires_at) <= Date.now()) return;
    submitting.current = true; setAttempted(true); setBusy(true); setError("");
    try {
      const response = await call(`/auth/native/requests/${requestId}/approve`, "POST", {}, AbortSignal.timeout(10000));
      const destination = appReturn(await response.json());
      setReturnURL(destination);
      // Only the validated one-use code, never a session/access token, leaves
      // this browser. The native app must still prove its PKCE verifier.
      window.location.assign(destination);
    } catch {
      // An uncertain approval is never automatically replayed.
      setError("Approval could not be confirmed. Return to the app and start a new sign-in request.");
    } finally { setBusy(false); }
  }

  return <main className="auth-shell"><section className="auth-card">
    <h1>Connect Onesa AI Platform</h1>
    {busy && <p role="status">Checking your sign-in request…</p>}
    {error && <p role="alert">{error}</p>}
    {signedOut && requestId && (method?.enabled && !method.unavailable ? <OnesaSignIn method={method} next={`/auth/native?request=${requestId}`} /> : <IdentityEntryStatus method={method} />)}
    {details && !returnURL && <>
      <p>Sign in to the {details.platform === "ios" ? "iPhone or iPad" : "Android"} app as <strong>{details.user.email}</strong>.</p>
      <p>The app can access your own conversations, documents, agent tasks and travel plans. Your existing Onesa permissions still apply.</p>
      <p>Continue only if you started this request in your installed app. You can close this page to cancel.</p>
      <button type="button" disabled={busy || attempted || details.status !== "pending"} onClick={() => void approve()}>Approve and return to app</button>
    </>}
    {returnURL && <p><a href={returnURL}>Return to Onesa AI Platform</a></p>}
    <p><a href="/">Return to web workspace</a></p>
  </section></main>;
}
