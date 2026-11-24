"use client";

import { useEffect, useRef, useState } from "react";
import { beginOnesaSignIn, registrationPageKey } from "../../../components/onesa-sign-in";
import { useLocale } from "../../../lib/i18n";

export default function ContinueSignIn() {
  const { locale } = useLocale(), de = locale === "de";
  const started = useRef(false), [error, setError] = useState("");
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const params = new URLSearchParams(window.location.search);
    let next = params.get("next") || "/";
    const fromRegistration = params.get("registration") === "complete";
    if (fromRegistration) {
      try {
        const stored = sessionStorage.getItem(registrationPageKey);
        if (stored && stored.startsWith("/") && !stored.startsWith("//") && !stored.includes("\\")) next = stored;
      } catch { /* The existing product OIDC flow can resume at the homepage. */ }
    }
    void beginOnesaSignIn(next, { reauthenticate: params.get("reauthenticate") === "true", fromRegistration })
      .catch(reason => setError(reason instanceof Error ? reason.message : "Sign-in is unavailable"));
  }, []);
  return <main className="auth-shell"><section className="auth-card">
    <h1>{de ? "Mit Onesa fortfahren" : "Continue with Onesa"}</h1>
    {error ? <>
      <p role="alert">{error}</p>
      <button type="button" className="send" onClick={() => window.location.reload()}>{de ? "Anmeldung erneut versuchen" : "Retry sign-in"}</button>
    </> : <p role="status">{de ? "Onesa-Konto wird geöffnet…" : "Opening your Onesa account…"}</p>}
  </section></main>;
}
