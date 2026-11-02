"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { ApiError, call } from "../lib/api";
import { useLocale } from "../lib/i18n";
import { parseIdentityMethod, type OnesaMethod } from "../lib/identity-method";

export type { OnesaMethod } from "../lib/identity-method";
type Identity = { id: string; email: string; display_name: string };
const IdentityMethodContext = createContext<OnesaMethod | null>(null);

export function OnesaIdentityProvider({ initialMethod, children }:
  { initialMethod: OnesaMethod; children: React.ReactNode }) {
  const [method, setMethod] = useState<OnesaMethod>({ ...initialMethod, pending: true });
  useEffect(() => {
    const controller = new AbortController();
    call("/auth/onesa/config", "GET", undefined, AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]))
      .then(response => response.json()).then(value => {
        const verified = parseIdentityMethod(value);
        if (!controller.signal.aborted) setMethod(verified);
      }).catch(reason => {
        if (controller.signal.aborted) return;
        // Only an older API's explicit missing route selects the native flow.
        setMethod({ enabled: false, account_url: null, unavailable: !(reason instanceof ApiError && reason.status === 404) });
      });
    return () => controller.abort();
  }, []);
  return <IdentityMethodContext.Provider value={method}>{children}</IdentityMethodContext.Provider>;
}

export function useOnesaIdentity() {
  return useContext(IdentityMethodContext);
}

export function IdentityEntryStatus({ method }: { method: OnesaMethod | null }) {
  const { locale } = useLocale(), de = locale === "de";
  return method?.unavailable ? <div>
    <p role="alert">{de ? "Die Anmeldemethode konnte nicht geladen werden. Bitte versuche es erneut." : "We could not load the sign-in method. Please try again."}</p>
    <button type="button" onClick={() => window.location.reload()}>{de ? "Erneut versuchen" : "Retry sign-in"}</button>
  </div> : <p role="status">{de ? "Anmeldung wird vorbereitet…" : "Preparing sign-in…"}</p>;
}

export async function beginOnesaSignIn(next: string, reauthenticate = false) {
  const response = await call("/auth/onesa/start", "POST", { next, reauthenticate }, AbortSignal.timeout(10000));
  const value = await response.json();
  const url = new URL(value.authorize_url);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname)))
    throw new Error("Onesa sign-in is unavailable. Please try again.");
  window.location.assign(url.href);
}

export default function OnesaSignIn({ method, next = "/", preserveDraft = false, onAuthenticated }:
  { method: OnesaMethod; next?: string; preserveDraft?: boolean; onAuthenticated?: (user: Identity) => void }) {
  const { locale } = useLocale(), de = locale === "de";
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [linking, setLinking] = useState(false);
  const pending = useRef(false), timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    let active = true;
    const state = new URLSearchParams(window.location.search).get("identity");
    void Promise.resolve().then(() => {
      if (!active) return;
      setLinking(state === "link_required");
      if (state === "cancelled") setError(de ? "Anmeldung abgebrochen. Du kannst es erneut versuchen." : "Sign-in was cancelled. You can try again.");
      if (state === "unavailable") setError(de ? "Die Anmeldung konnte nicht abgeschlossen werden. Bitte erneut versuchen." : "Sign-in could not finish. Please try again.");
      if (state === "access_required") setError(de ? "Dein Onesa-Konto hat noch keinen Zugriff auf AI Platform. Bitte deinen Administrator um Zugriff." : "Your Onesa account does not have AI Platform access yet. Ask your administrator to grant access.");
    });
    return () => { active = false; if (timer.current) clearInterval(timer.current); };
  }, [de]);

  async function start() {
    if (pending.current || method.pending || method.unavailable) return;
    pending.current = true; setBusy(true); setError("");
    try {
      if (preserveDraft && onAuthenticated) {
        window.open("/auth/continue?next=/auth/complete", "_blank", "noopener,noreferrer");
        const deadline = Date.now() + 300000;
        let polling = false;
        timer.current = setInterval(async () => {
          if (Date.now() > deadline) {
            if (timer.current) clearInterval(timer.current);
            pending.current = false; setBusy(false);
            setError(de ? "Die Anmeldung ist noch nicht bestätigt. Dein Entwurf bleibt erhalten." : "Sign-in has not been confirmed. Your draft is still here.");
            return;
          }
          if (polling) return;
          polling = true;
          try {
            const response = await call("/auth/me", "GET", undefined, AbortSignal.timeout(5000));
            const user: Identity = await response.json();
            if (timer.current) clearInterval(timer.current);
            onAuthenticated(user); pending.current = false; setBusy(false);
          } catch { /* The separate sign-in window may still be open. */ }
          finally { polling = false; }
        }, 2000);
      } else {
        const destination = new URL(window.location.href);
        destination.searchParams.delete("identity");
        await beginOnesaSignIn(next === "/" ? destination.pathname + destination.search : next);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in is unavailable");
      pending.current = false; setBusy(false);
    }
  }

  async function link(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || method.pending || method.unavailable) return;
    const form = event.currentTarget, data = new FormData(form);
    pending.current = true; setBusy(true); setError("");
    try {
      const response = await call("/auth/onesa/link", "POST", { email: data.get("email"), current_password: data.get("password") });
      const value = await response.json();
      window.location.replace(value.next.startsWith("/") && !value.next.startsWith("//") ? value.next : "/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The account could not be connected");
      pending.current = false; setBusy(false);
      const password = form.querySelector<HTMLInputElement>('input[type="password"]');
      if (password) password.value = "";
    }
  }

  return <div className="onesa-shared-signin">
    <p>{de ? "Ein Onesa-Konto für AI Platform, Drone und Robot. Dein Administrator legt deinen Zugriff fest." : "One Onesa account for AI Platform, Drone and Robot. Your administrator manages which applications you can use."}</p>
    {linking ? <form onSubmit={link}>
      <h2>{de ? "Bisheriges AI-Konto verbinden" : "Connect your existing AI account"}</h2>
      <p>{de ? "Bestätige dein bisheriges AI-Passwort einmalig. Deine Gespräche und Dateien bleiben deinem Konto zugeordnet." : "Confirm your existing AI password once. Your conversations and files stay with your account."}</p>
      <label>{de ? "E-Mail" : "Email"}<input name="email" type="email" autoComplete="username" required disabled={busy}/></label>
      <label>{de ? "Bisheriges AI-Passwort" : "Existing AI password"}<input name="password" type="password" autoComplete="current-password" required disabled={busy}/></label>
      <button className="send" disabled={busy || method.pending}>{busy ? (de ? "Wird verbunden…" : "Connecting…") : (de ? "Konto verbinden" : "Connect account")}</button>
    </form> : <button className="send" type="button" onClick={start} disabled={busy || method.pending}>
      {busy ? (de ? "Anmeldung wird bestätigt…" : "Waiting for sign-in…") : (de ? "Mit Onesa fortfahren" : "Continue with Onesa")}
    </button>}
    {busy && preserveDraft && <p role="status">{de ? "Schließe die Anmeldung im neuen Fenster ab. Dein Entwurf bleibt hier erhalten." : "Finish signing in in the new window. Your draft stays here."}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {method.account_url && <p><a href={method.account_url + "/register"}>{de ? "Onesa-Konto erstellen" : "Create an Onesa account"}</a> · <a href={method.account_url}>{de ? "Konto und Zugriff" : "Account and access"}</a></p>}
  </div>;
}
