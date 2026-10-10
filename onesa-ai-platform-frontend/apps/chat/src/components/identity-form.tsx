"use client";
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { call } from "../lib/api";

export default function IdentityForm({ invitation = false }: { invitation?: boolean }) {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
    window.history.replaceState(null, "", window.location.pathname);
    let active = true;
    void Promise.resolve(value).then(value => { if (active) setToken(value); });
    return () => { active = false; };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      if (invitation) {
        await call("/auth/register", "POST", { email: form.get("email"), password: form.get("password"), display_name: form.get("name"), invitation_token: token });
        window.location.assign("/");
      } else if (token) {
        await call("/auth/recovery/complete", "POST", { token, new_password: form.get("password") });
        setToken(""); setMessage("Password changed. Your old sessions have been revoked. Sign in with your new password.");
      } else {
        await call("/auth/recovery/request", "POST", { email: form.get("email") });
        setMessage("If this account is eligible, a recovery message has been queued. This does not confirm delivery.");
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : "Request failed"); }
    finally { setBusy(false); }
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
