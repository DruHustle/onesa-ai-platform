"use client";

import { useEffect, useRef, useState } from "react";
import { beginOnesaSignIn } from "../../../components/onesa-sign-in";
import { useLocale } from "../../../lib/i18n";

export default function ContinueSignIn() {
  const { locale } = useLocale(), de = locale === "de";
  const started = useRef(false), [error, setError] = useState("");
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const params = new URLSearchParams(window.location.search);
    void beginOnesaSignIn(params.get("next") || "/", params.get("reauthenticate") === "true")
      .catch(reason => setError(reason instanceof Error ? reason.message : "Sign-in is unavailable"));
  }, []);
  return <main className="auth-shell"><section className="auth-card">
    <h1>{de ? "Mit Onesa fortfahren" : "Continue with Onesa"}</h1>
    {error ? <p role="alert">{error} <a href="/">{de ? "Zurück zur Anmeldung" : "Return to sign in"}</a></p> : <p role="status">{de ? "Onesa-Konto wird geöffnet…" : "Opening your Onesa account…"}</p>}
  </section></main>;
}
