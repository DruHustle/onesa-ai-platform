"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { call } from "../lib/api";

export default function IdentityForm({ invitation = false }: { invitation?: boolean }) {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const currentToken = useRef("");
  const revision = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    let active = true;
    const consume = () => {
      if (window.location.hash) {
        currentToken.current = new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
        // Preserve the query and router history state; never persist the link token.
        window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
        revision.current++;
        pending.current?.abort();
        pending.current = null;
      }
      const observed = revision.current;
      // The ref survives Strict Mode's effect replay after the fragment is stripped.
      void Promise.resolve().then(() => {
        if (active && observed === revision.current) {
          setToken(currentToken.current); setMessage(""); setBusy(false);
        }
      });
    };
    consume();
    window.addEventListener("hashchange", consume);
    window.addEventListener("popstate", consume);
    return () => {
      active = false; mounted.current = false;
      pending.current?.abort(); pending.current = null;
      window.removeEventListener("hashchange", consume);
      window.removeEventListener("popstate", consume);
    };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const request = new AbortController(), observed = revision.current, submittedToken = currentToken.current;
    pending.current = request; setBusy(true); setMessage("");
    const isCurrent = () => mounted.current && revision.current === observed && pending.current === request;
    const form = new FormData(event.currentTarget);
    try {
      if (invitation) {
        await call("/auth/register", "POST", { email: form.get("email"), password: form.get("password"), display_name: form.get("name"), invitation_token: submittedToken }, request.signal);
        if (isCurrent()) window.location.assign("/");
      } else if (submittedToken) {
        await call("/auth/recovery/complete", "POST", { token: submittedToken, new_password: form.get("password") }, request.signal);
        if (isCurrent()) {
          currentToken.current = ""; setToken(""); setMessage("Password changed. Your old sessions have been revoked. Sign in with your new password.");
        }
      } else {
        await call("/auth/recovery/request", "POST", { email: form.get("email") }, request.signal);
        if (isCurrent()) setMessage("If this account is eligible, a recovery message has been queued. This does not confirm delivery.");
      }
    } catch (error) { if (isCurrent()) setMessage(error instanceof Error ? error.message : "Request failed"); }
    finally { if (isCurrent()) { pending.current = null; setBusy(false); } }
  }
  return <main className="auth-shell"><section className="auth-card"><h1>{invitation ? "Accept invitation" : "Account recovery"}</h1>
    {invitation && !token ? <p role="alert">Open your private invitation link. An invitation is required.</p> : <form onSubmit={submit}>
      {(invitation || !token) && <label>Email<input type="email" name="email" autoComplete="email" required /></label>}
      {invitation && <label>Display name<input name="name" maxLength={80} required /></label>}
      {(invitation || token) && <label>New password<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>}
      <button disabled={busy}>{busy ? "Please wait…" : invitation ? "Create invited account" : token ? "Set new password" : "Request recovery"}</button>
    </form>}
    <p role="status">{message}</p><Link href="/">Back to sign in</Link></section></main>;
}
