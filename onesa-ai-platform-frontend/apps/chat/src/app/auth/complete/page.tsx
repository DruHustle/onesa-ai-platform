"use client";

import { useEffect, useState } from "react";
import { call } from "../../../lib/api";
import { useLocale } from "../../../lib/i18n";

export default function SignInComplete() {
  const { locale } = useLocale(), de = locale === "de";
  const [status, setStatus] = useState<"checking" | "complete" | "unavailable">("checking");
  useEffect(() => {
    const controller = new AbortController();
    call("/auth/me", "GET", undefined, AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]))
      .then(() => { if (!controller.signal.aborted) setStatus("complete"); })
      .catch(() => { if (!controller.signal.aborted) setStatus("unavailable"); });
    return () => controller.abort();
  }, []);
  return <main className="auth-shell"><section className="auth-card">
    <h1>{de ? "Zurück zu deinem Arbeitsbereich" : "Return to your workspace"}</h1>
    {status === "checking" ? <p role="status">{de ? "Anmeldung wird geprüft…" : "Checking your sign-in…"}</p>
      : status === "complete" ? <p>{de ? "Deine Onesa-Anmeldung ist bestätigt. Kehre zum ursprünglichen Fenster zurück, um weiterzuarbeiten." : "Your Onesa sign-in is confirmed. Return to the window where you started to continue your work."}</p>
      : <p role="alert">{de ? "Deine Anmeldung konnte nicht bestätigt werden. Dein ursprünglicher Arbeitsbereich bleibt geöffnet." : "We could not confirm your sign-in. Your original workspace remains open."}</p>}
    <a href="/">{de ? "AI Platform hier öffnen" : "Open AI Platform here"}</a>
  </section></main>;
}
