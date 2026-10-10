"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import FeatureShell from "../../components/feature-shell";
import { api, type SafeUser, type SessionList } from "../../lib/api";

export default function Settings() {
  const [user, setUser] = useState<SafeUser | null>(null);
  const [sessions, setSessions] = useState<SessionList | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const [profile, active] = await Promise.all([
      api("GET /auth/me"),
      api("GET /auth/sessions"),
    ]);
    setUser(profile);
    setSessions(active);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api("GET /auth/me", { signal: controller.signal }),
      api("GET /auth/sessions", { signal: controller.signal }),
    ])
      .then(([profile, active]) => {
        setUser(profile);
        setSessions(active);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, []);

  async function submit(
    event: React.FormEvent<HTMLFormElement>,
    action: "profile" | "password" | "sessions" | "export" | "delete",
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (action === "profile") {
        await api("PATCH /auth/profile", {
          body: { display_name: String(data.get("display_name") || "").trim() },
        });
        setNotice("Display name saved.");
      } else if (action === "password") {
        const newPassword = String(data.get("new_password") || "");
        if (newPassword !== data.get("confirm_password"))
          throw new Error("New passwords must match.");
        await api("POST /auth/password", {
          body: {
            current_password: String(data.get("current_password") || ""),
            new_password: newPassword,
          },
        });
        setNotice(
          "Password changed. All previous sessions were signed out; this browser has a new session.",
        );
      } else if (action === "export") {
        const exported = await api("POST /account/export", {
          body: {
            current_password: String(data.get("current_password") || ""),
          },
        });
        const url = URL.createObjectURL(
          new Blob([JSON.stringify(exported, null, 2)], {
            type: "application/json",
          }),
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = "onesa-account-export.json";
        link.click();
        URL.revokeObjectURL(url);
        setNotice(
          "Account export downloaded. Store it securely; it contains your private content.",
        );
      } else if (action === "delete") {
        if (data.get("confirmation") !== "DELETE MY ACCOUNT")
          throw new Error("Type DELETE MY ACCOUNT to confirm.");
        await api("POST /account/delete", {
          body: {
            current_password: String(data.get("current_password") || ""),
            confirmation: "DELETE MY ACCOUNT",
          },
        });
        setUser(null);
        setSessions(null);
        setNotice(
          "Your account and live application data were deleted. Backup retention is handled separately.",
        );
        return;
      } else {
        await api("POST /auth/sessions/revoke-others", {
          body: {
            current_password: String(data.get("current_password") || ""),
          },
        });
        setNotice("Other sessions signed out. This browser remains signed in.");
      }
      await load();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      form
        .querySelectorAll<HTMLInputElement>('input[type="password"]')
        .forEach((input) => {
          input.value = "";
        });
      setBusy(false);
    }
  }

  return (
    <FeatureShell title="Account settings">
      <p className="intro">
        Manage your profile and account access. Interface language is saved in
        this browser using the language menu.
      </p>
      {error && (
        <p role="alert" className="error">
          {error} <Link href="/">Return to Chat to sign in.</Link>
        </p>
      )}
      <p role="status" aria-live="polite">
        {notice}
      </p>
      {user && (
        <>
          <form
            className="feature-card"
            onSubmit={(event) => submit(event, "profile")}
          >
            <h2>Profile</h2>
            <p>Signed in as {user.email}</p>
            <label>
              Display name
              <input
                name="display_name"
                defaultValue={user.display_name}
                required
                maxLength={80}
                autoComplete="nickname"
              />
            </label>
            <button className="send" disabled={busy}>
              Save display name
            </button>
          </form>
          <form
            className="feature-card"
            onSubmit={(event) => submit(event, "password")}
          >
            <h2>Change password</h2>
            <label>
              Current password
              <input
                name="current_password"
                type="password"
                required
                maxLength={128}
                autoComplete="current-password"
              />
            </label>
            <label>
              New password
              <input
                name="new_password"
                type="password"
                required
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
              />
            </label>
            <label>
              Confirm new password
              <input
                name="confirm_password"
                type="password"
                required
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
              />
            </label>
            <p>
              Use at least 12 characters. Changing your password signs out every
              previous session.
            </p>
            <button className="send" disabled={busy}>
              Change password
            </button>
          </form>
          <section className="feature-card" aria-labelledby="sessions-heading">
            <h2 id="sessions-heading">Active sessions</h2>
            {sessions && (
              <>
                <p>
                  {sessions.total} active{" "}
                  {sessions.total === 1 ? "session" : "sessions"}. Showing up to{" "}
                  {sessions.limit} most recent sessions.
                </p>
                <ul>
                  {sessions.items.map((session) => (
                    <li key={session.id}>
                      {session.current ? "This browser" : "Other session"}:
                      signed in {new Date(session.created_at).toLocaleString()};
                      expires {new Date(session.expires_at).toLocaleString()}.
                    </li>
                  ))}
                </ul>
              </>
            )}
            <form onSubmit={(event) => submit(event, "sessions")}>
              <label>
                Password to sign out other sessions
                <input
                  name="current_password"
                  type="password"
                  required
                  maxLength={128}
                  autoComplete="current-password"
                />
              </label>
              <button disabled={busy}>Sign out other sessions</button>
            </form>
          </section>
          <form
            className="feature-card"
            onSubmit={(event) => submit(event, "export")}
          >
            <h2>Export your data</h2>
            <p>
              Download your profile, conversations, extracted documents, tool
              runs and trips as JSON. Credentials and derived vectors are
              excluded. Large exports require support; data is never silently
              truncated.
            </p>
            <label>
              Password to export your data
              <input
                name="current_password"
                type="password"
                required
                maxLength={128}
                autoComplete="current-password"
              />
            </label>
            <button disabled={busy}>Download account export</button>
          </form>
          <form
            className="feature-card"
            onSubmit={(event) => submit(event, "delete")}
          >
            <h2>Delete your account</h2>
            <p>
              This permanently deletes your profile, sessions, conversations,
              documents and their search vectors, tool runs and trips from the
              live application. Stop active chat and tool runs first. Export
              anything you want to keep. Backup copies require separate
              retention processing.
            </p>
            <label>
              Password to delete your account
              <input
                name="current_password"
                type="password"
                required
                maxLength={128}
                autoComplete="current-password"
              />
            </label>
            <label>
              Type DELETE MY ACCOUNT to confirm
              <input name="confirmation" required autoComplete="off" />
            </label>
            <button disabled={busy}>Delete my account permanently</button>
          </form>
        </>
      )}
    </FeatureShell>
  );
}
