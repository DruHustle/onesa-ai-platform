"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, call, ApiError } from "../lib/api";
import { useLocale } from "../lib/i18n";
import FeatureShell from "./feature-shell";
type Identity = { id: string };
/** The original task stays mounted during same-user reauthentication. */
export default function RequireSession({
  title,
  destination,
  children,
}: {
  title: string;
  destination: "/travel" | "/knowledge" | "/industrial" | "/agents";
  children: React.ReactNode;
}) {
  const { locale } = useLocale(),
    de = locale === "de";
  const [identity, setIdentity] = useState<Identity | null>(null),
    [checking, setChecking] = useState(true),
    [expired, setExpired] = useState(false),
    [error, setError] = useState("");
  const [busy, setBusy] = useState(false),
    [loginEpoch, setLoginEpoch] = useState(0),
    pending = useRef(false),
    workspace = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([
      controller.signal,
      AbortSignal.timeout(8000),
    ]);
    api("GET /auth/me", { signal })
      .then((user) => {
        if (!signal.aborted) setIdentity(user);
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setExpired(true);
        if (!(reason instanceof ApiError && reason.status === 401))
          setError("We could not verify your session. Please sign in again.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false);
      });
    const lost = () => {
      setError("");
      setExpired(true);
    };
    window.addEventListener("onesa-session-expired", lost);
    return () => {
      controller.abort();
      window.removeEventListener("onesa-session-expired", lost);
    };
  }, []);
  useEffect(() => {
    if (!loginEpoch || expired) return;
    const heading = workspace.current?.querySelector("h1");
    if (heading) {
      heading.tabIndex = -1;
      heading.focus();
    }
  }, [loginEpoch, expired]);
  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const form = event.currentTarget,
      data = new FormData(form);
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      const response = await call(
        "/auth/login",
        "POST",
        { email: data.get("email"), password: data.get("password") },
        AbortSignal.timeout(15000),
      );
      const user: Identity = await response.json();
      if (identity && identity.id !== user.id) {
        const url = new URL(window.location.href);
        for (const key of [...url.searchParams.keys()]) if (key.startsWith("page_") || key === "trip") url.searchParams.delete(key);
        window.history.replaceState(window.history.state, "", url);
        window.dispatchEvent(new Event("onesa-record-page"));
      }
      setIdentity(user);
      setExpired(false);
      setLoginEpoch((previous) => previous + 1);
      form.reset();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  const blocked = !identity || expired;
  return (
    <>
      {blocked && (
        <FeatureShell title={title}>
          {checking ? (
            <p role="status">
              {de ? "Sitzung wird geprüft…" : "Checking your session…"}
            </p>
          ) : (
            <>
              <p
                className="intro"
                role={expired && identity ? "alert" : undefined}
              >
                {expired && identity
                  ? de
                    ? "Deine Sitzung ist abgelaufen oder konnte nicht bestätigt werden. Dein Entwurf bleibt in diesem Fenster erhalten. Melde dich mit demselben Konto an und prüfe ihn vor dem erneuten Speichern. Anfragen werden nicht automatisch wiederholt."
                    : "Your session expired or could not be verified. Your draft is kept in this window. Sign in with the same account and review it before saving again. Requests are never replayed automatically."
                  : de
                    ? "Melde dich an, bevor du in deinem geschützten Arbeitsbereich beginnst."
                    : "Sign in before starting work in your protected workspace."}
              </p>
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <form
                className="feature-card session-signin"
                onSubmit={signIn}
                aria-label={de ? "Anmelden" : "Sign in"}
              >
                <fieldset disabled={busy}>
                  <label>
                    {de ? "E-Mail" : "Email"}
                    <input
                      name="email"
                      autoFocus={expired && Boolean(identity)}
                      type="email"
                      autoComplete="username"
                      required
                    />
                  </label>
                  <label>
                    {de ? "Passwort" : "Password"}
                    <input
                      name="password"
                      type="password"
                      autoComplete="current-password"
                      required
                    />
                  </label>
                  <button className="send">
                    {busy
                      ? de
                        ? "Anmeldung…"
                        : "Signing in…"
                      : de
                        ? "Anmelden und fortfahren"
                        : "Sign in and continue"}
                  </button>
                </fieldset>
              </form>
              <p>
                {de
                  ? "Bei Anmeldung mit einem anderen Konto wird die bisherige Arbeit verworfen, damit Konten getrennt bleiben."
                  : "Signing in with a different account clears the previous workspace to keep accounts separate."}
              </p>
              <Link href={`/?next=${encodeURIComponent(destination)}`}>
                {de ? "Konto erstellen" : "Create an account"}
              </Link>
            </>
          )}
        </FeatureShell>
      )}
      {identity && (
        <div key={identity.id} ref={workspace} hidden={blocked}>
          <fieldset className="session-workspace" disabled={blocked}>
            {children}
          </fieldset>
        </div>
      )}
    </>
  );
}
