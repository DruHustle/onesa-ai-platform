"use client";
import {useRecordPage, RecordPageControls, useRecordSelection} from "../lib/record-page";
import ApplicationsNav from "../components/applications-nav";
import ProductionWorkspaceCue from "../components/production-workspace-cue";
import DocumentationNav from "../components/documentation-nav";
import IndustrialNav from "../components/industrial-nav";
import DocumentationHelp from "../components/documentation-help";
import {documentationUrls} from "../lib/documentation";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";

const MessageContent = lazy(() => import("../components/message-content"));

type User = { id: string; display_name: string };
type Conversation = { id: string; title: string };
type Message = {
  id: string;
  role: string;
  content: { text: string; sources?: { document_id: string; title: string }[] };
};
import { chatEvents } from "../../../../packages/api-client/sse";
import { call, csrf, api, ApiError } from "../lib/api";
import Link from "next/link";
import { LanguageSelect, useLocale } from "../lib/i18n";
export default function Chat() {
  const { copy, locale } = useLocale();
  const [model, setModel] = useState<{
    backend: string;
    model_identifier: string;
    real_inference: boolean;
  } | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [linkedDocument, setLinkedDocument] = useState<{id: string; title: string} | null>(null);
  const [documentIds, setDocumentIds] = useState<string[]>([]);
  const [knowledgeReady, setKnowledgeReady] = useState(false);
  const [user, setUser] = useState<User | null>(null),
    [checking, setChecking] = useState(true),
    [signup, setSignup] = useState(false);
  const [selectedLocation, setSelectedLocation] = useRecordSelection("conversation");
  const history = useRecordPage<Conversation>("/conversations", user?.id || "");
  const knowledge = useRecordPage<{id: string; title: string}>("/knowledge/documents", user?.id || "");
  const {items: list, setItems: setList} = history;
  const documents = linkedDocument && !knowledge.items.some(item => item.id === linkedDocument.id)
    ? [linkedDocument, ...knowledge.items] : knowledge.items;
  const [selected, setSelected] = useState<string | null>(null),
    [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(""),
    [partial, setPartial] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [menu, setMenu] = useState(false);
  const followLatest = useRef(true);
  const sidebar = useRef<HTMLElement | null>(null);
  const toggle = useRef<HTMLButtonElement | null>(null);
  const abort = useRef<AbortController | null>(null),
    bottom = useRef<HTMLDivElement | null>(null),
    entry = useRef<HTMLTextAreaElement | null>(null);
  const credentialDraft = useRef<HTMLInputElement | null>(null);
  const detailRequest = useRef(0);
  const identityEpoch = useRef(0), draftOwner = useRef<string | null>(null);
  const refreshList = history.reload;
  const acceptUser = useCallback((current: User) => {
    identityEpoch.current += 1;
    if (draftOwner.current && draftOwner.current !== current.id) {
      setInput(""); setMessages([]); setSelected(null); detailRequest.current += 1;
      const url = new URL(window.location.href);
      url.searchParams.delete("conversation");
      for (const key of [...url.searchParams.keys()]) if (key.startsWith("page_")) url.searchParams.delete(key);
      window.history.replaceState(window.history.state, "", url);
      window.dispatchEvent(new Event("onesa-record-page"));
    }
    draftOwner.current = current.id;
    // Ordinary chat does not depend on the optional document list.
    setKnowledgeReady(!new URLSearchParams(window.location.search).get("document"));
    const intended = new URLSearchParams(window.location.search).get("next");
    if (intended === "/agents" || intended === "/travel" || intended === "/knowledge" || intended === "/industrial") {window.location.replace(intended); return;}
    setLinkedDocument(null); setDocumentIds([]);
    setUser(current);
  }, []);
  useEffect(() => {
    const expired = () => {
      identityEpoch.current += 1; detailRequest.current += 1;
      abort.current?.abort();
      setUser(null); setBusy(false); setMessages([]); setSelected(null);
      setLinkedDocument(null); setDocumentIds([]); setKnowledgeReady(false); setPartial(null);
      setError("Your session expired. Sign in with the same account to continue your draft.");
    };
    window.addEventListener("onesa-session-expired", expired);
    return () => window.removeEventListener("onesa-session-expired", expired);
  }, []);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]);
    api("GET /auth/me", {signal})
      .then((u) => {
        if (active) acceptUser(u);
      })
      .catch((failure: unknown) => {
        if (!active) return;
        if (failure instanceof ApiError && failure.status === 403 && failure.code === "invitation_required") setError(failure.message);
        else if (!(failure instanceof ApiError && failure.status === 401)) setUnavailable(true);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
      controller.abort();
      abort.current?.abort();
    };
  }, [acceptUser, sessionAttempt]);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]);
    if (user)
      call("/models", "GET", undefined, signal)
        .then((r) => r.json())
        .then((data) => { if (active) setModel(data.items[0]); })
        .catch((e) => { if (active) setError(e.message); });
    if (user) {
      const id = new URLSearchParams(window.location.search).get("document");
      if (id) api("GET /knowledge/documents/{identifier}", {params: {identifier: id}, signal})
        .then(document => {
          if (!active) return;
          setLinkedDocument(document); setDocumentIds([document.id]); setKnowledgeReady(true);
        })
        .catch(() => { if (active) setError("The selected document is unavailable or access could not be verified. Open Knowledge or reload to retry."); });
    }
    return () => {
      active = false;
      controller.abort();
    };
  }, [user]);
  useEffect(() => {
    if (followLatest.current) bottom.current?.scrollIntoView({ behavior: "auto" });
  }, [messages, partial]);
  const closeMenu = useCallback(() => {
    setMenu(false);
    requestAnimationFrame(() => toggle.current?.focus());
  }, []);
  useEffect(() => {
    if (!menu) return;
    const elements = () =>
      Array.from(
        sidebar.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), a[href]",
        ) || [],
      ).filter((el) => el.getClientRects().length);
    elements()[0]?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeMenu();
      }
      if (event.key === "Tab") {
        const controls = elements(),
          first = controls[0],
          last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", keyboard);
    return () => document.removeEventListener("keydown", keyboard);
  }, [menu, closeMenu]);
  async function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (checking || busy || unavailable) return;
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const data = {
        email: form.get("email"),
        password: form.get("password"),
        ...(signup ? { display_name: form.get("name") } : {}),
      };
      const response = await call(
        signup ? "/auth/register" : "/auth/login",
        "POST",
        data,
      );
      acceptUser(await response.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    if (!user || busy || selectedLocation === selected) return () => controller.abort();
    const sequence = ++detailRequest.current;
    const read = selectedLocation ? call(`/conversations/${encodeURIComponent(selectedLocation)}`, "GET", undefined,
      AbortSignal.any([controller.signal, AbortSignal.timeout(8000)])).then(response => response.json()) : Promise.resolve({messages: []});
    read.then(result => {
      if (controller.signal.aborted || sequence !== detailRequest.current) return;
      setMessages(result.messages); setSelected(selectedLocation); setPartial(null);
    }).catch(() => {if (!controller.signal.aborted) setError("Unable to reopen this conversation. Select it again to retry.");});
    return () => controller.abort();
  }, [user, selectedLocation, selected, busy]);

  async function open(id: string) {
    if (busy) return;
    setError("");
    try {
      const request = ++detailRequest.current, epoch = identityEpoch.current;
      const r = await call(`/conversations/${id}`, "GET", undefined, AbortSignal.timeout(8000));
      const result = await r.json();
      if (request !== detailRequest.current || epoch !== identityEpoch.current) return;
      setMessages(result.messages);
      setSelectedLocation(id);
      setSelected(id);
      setPartial(null);
      setMenu(false);
      entry.current?.focus();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function create(): Promise<string> {
    const epoch = identityEpoch.current;
    const r = await call("/conversations", "POST", {
      title: input.trim().slice(0, 70) || "New conversation",
    });
    const row = await r.json();
    if (epoch !== identityEpoch.current) return row.id;
    setSelected(row.id);
    setSelectedLocation(row.id);
    setMessages([]);
    await refreshList();
    return row.id;
  }
  const [canStop, setCanStop] = useState(false);
  const activeRun = useRef<{ conversation_id: string; run_id: string } | null>(null);
  async function stop() {
    const run = activeRun.current;
    if (!run) return;
    try {
      const response = await call(`/conversations/${run.conversation_id}/cancel`, "POST", { run_id: run.run_id });
      if (!response.ok) throw new Error("Unable to confirm cancellation; retry Stop.");
      abort.current?.abort();
    } catch {
      setError("Unable to confirm cancellation; retry Stop.");
    }
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim() || busy || !knowledgeReady) return;
    const content = input, epoch = identityEpoch.current;
    detailRequest.current += 1;
    setBusy(true);
    setError("");
    setInput("");
    let id = selected;
    try {
      if (!id) id = await create();
      if (epoch !== identityEpoch.current) return;
      setMessages((previous) => [
        ...previous,
        { id: "pending", role: "user", content: { text: content } },
      ]);
      setPartial("");
      const controller = new AbortController();
      abort.current = controller;
      const response = await fetch("/api/v1/chat/completions", {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
        body: JSON.stringify({
          conversation_id: id,
          content,
          stream: true,
          document_ids: documentIds,
        }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error?.message || "Unable to generate response");
      }
      if (!response.body) throw new Error("Streaming unavailable");
      for await (const event of chatEvents(response.body)) {
        if (epoch !== identityEpoch.current) break;
        if (event.kind === "message_start") { activeRun.current = event; setCanStop(true); }
        if (event.kind === "content_delta") setPartial(p => (p || "") + event.text);
        if (event.kind === "error") throw new Error(event.message);
        if (event.kind === "message_end") setModel(event.model);
      }
      setPartial(null);
    } catch (e) {
      if (epoch !== identityEpoch.current) return;
      setError(
        (e as Error).name === "AbortError"
          ? "Generation stopped."
          : (e as Error).message,
      );
    } finally {
      if (epoch === identityEpoch.current) {
      abort.current = null;
      activeRun.current = null;
      setCanStop(false);
      setBusy(false);
      if (id) {
        try {
          const r = await call(`/conversations/${id}`);
          const saved = await r.json();
          if (epoch === identityEpoch.current) setMessages(saved.messages);
        } catch {
          /* Keep the existing generation error visible if history reload fails. */
        }
      }
      refreshList();
      entry.current?.focus();
      }
    }
  }
  async function rename() {
    const title = window.prompt(
      "Conversation title",
      list.find((c) => c.id === selected)?.title,
    );
    if (!title || !selected) return;
    try {
      await call(`/conversations/${selected}`, "PATCH", { title });
      await refreshList();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function remove() {
    if (
      !selected ||
      !window.confirm("Delete this conversation and its messages?")
    )
      return;
    try {
      await call(`/conversations/${selected}`, "DELETE");
      setSelectedLocation(null);
      setSelected(null);
      setMessages([]);
      setPartial(null);
      await refreshList();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function logout() {
    detailRequest.current += 1;
    try {
      await call("/auth/logout", "POST");
      identityEpoch.current += 1;
      setUser(null);
      setLinkedDocument(null);
      setDocumentIds([]);
      setKnowledgeReady(false);
      setMessages([]);
      setSelected(null);
      setList([]);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!user)
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="brand">
            Onesa <span>AI Platform</span>
          </div>
          <h1>{signup ? copy.createTitle : copy.welcome}</h1>
          <p>{locale==='de'?'Gespräche führen, eigenes Wissen nutzen und Aufgaben mit geführten Werkzeugen bearbeiten. Onesa AI Platform ist unser geschützter KI-Arbeitsbereich.':'Talk through ideas, use your own knowledge and work with guided tools. Onesa AI Platform is our protected AI workspace.'}</p>
          <p>{signup?(locale==='de'?'Die Registrierung hängt von der Freigabe dieser Umgebung ab. Wenn eine Einladung erforderlich ist, verwenden Sie Ihren privaten Einladungslink.':'Registration depends on this environment’s access policy. If an invitation is required, use your private invitation link.'):(locale==='de'?'Mit Ihrem bestehenden Plattformkonto anmelden. Ein Plattformkonto gewährt keinen Administrator-, Engineering- oder Robot-Zugriff.':'Sign in with your existing platform account. A platform account does not grant administrator, engineering or Robot access.')}</p>
          <nav className="auth-orientation" aria-label={locale==='de'?'Plattform kennenlernen':'Learn about the platform'}><a href={documentationUrls.public+'/docs/public/ai-platform'}>{locale==='de'?'Produkt und Funktionen':'Product and capabilities'}</a><a href={documentationUrls.public+'/docs/public/quickstart'}>{locale==='de'?'Entwickler-Schnellstart':'Developer quickstart'}</a></nav>
          {checking && <p role="status">{copy.opening}</p>}
          <Link href="/recovery">{locale === "de" ? "Passwort vergessen?" : "Forgot password?"}</Link>
          {unavailable && <div role="alert"><p>{locale === "de" ? "Der Dienst ist derzeit nicht erreichbar. Bitte versuchen Sie es erneut." : "The service is unavailable. Please retry before signing in."}</p><button type="button" onClick={() => {
            setChecking(true);
            setUnavailable(false);
            setError("");
            setSessionAttempt(previous => previous + 1);
            credentialDraft.current?.focus();
          }}>{locale === "de" ? "Erneut versuchen" : "Retry connection"}</button></div>}
          <form onSubmit={authenticate} aria-busy={checking || busy}>
            {signup && (
              <label>
                {copy.name}
                <input
                  name="name"
                  disabled={busy}
                  onFocus={event => { credentialDraft.current = event.currentTarget; }}
                  autoComplete="name"
                  required
                  maxLength={80}
                />
              </label>
            )}
            <label>
              {copy.email}
              <input name="email" type="email" autoComplete="email" required disabled={busy}
                onFocus={event => { credentialDraft.current = event.currentTarget; }}/>
            </label>
            <label>
              {copy.password}
              <input
                name="password"
                disabled={busy}
                onFocus={event => { credentialDraft.current = event.currentTarget; }}
                type="password"
                autoComplete={signup ? "new-password" : "current-password"}
                required
                minLength={12}
                maxLength={128}
              />
            </label>
            {error && (
              <div className="error" role="alert">
                {error}
              </div>
            )}
            <button className="send" disabled={busy || checking || unavailable}>
              {busy ? copy.wait : signup ? copy.create : copy.signIn}
            </button>
          </form>
          <LanguageSelect />
          <button
            className="switch"
            disabled={checking || busy || unavailable}
            onClick={() => {
              setSignup(!signup);
              setError("");
            }}
          >
            {signup ? copy.existing : copy.newAccount}
          </button>
        </section>
      </main>
    );
  return (
    <main className="workspace">
      <aside
        ref={sidebar}
        className={`sidebar ${menu ? "open" : ""}`}
        role={menu ? "dialog" : undefined}
        aria-modal={menu ? true : undefined}
        aria-label="Conversation navigation"
      >
        {menu && (
          <button
            className="mobile-toggle"
            aria-label="Close conversations"
            onClick={closeMenu}
          >
            Close ×
          </button>
        )}
        <div className="brand">
          Onesa <span>AI Platform</span>
        </div>
        <div className="feature-nav">
          <Link href="/" aria-current="page">{copy.chat}</Link>
          <Link href="/knowledge">{copy.knowledge}</Link>
          <Link href="/agents">{copy.agents}</Link>
          <Link href="/travel">{copy.travel}</Link>
          <IndustrialNav />
          <Link href="/settings" lang="en">Account settings</Link>
          <DocumentationNav />
        </div>
        <ApplicationsNav />
        <button
          className="new"
          disabled={busy}
          onClick={() => {
            detailRequest.current += 1;
            setSelectedLocation(null);
            setSelected(null);
            setMessages([]);
            setPartial(null);
            setMenu(false);
            entry.current?.focus();
          }}
        >
          {copy.newConversation}
        </button>
        <nav aria-label="Conversations">
          <RecordPageControls page={history} />
          {list.map((c) => (
            <button
              key={c.id}
              className={`conversation ${c.id === selected ? "selected" : ""}`}
              disabled={busy}
              onClick={() => open(c.id)}
            >
              {c.title}
            </button>
          ))}
          {!history.loading && !history.error && !list.length && (
            <p className="caption">Your saved conversations appear here.</p>
          )}
        </nav>
        <LanguageSelect />
        <div className="account">
          <span>{user.display_name}</span>
          <button disabled={busy} onClick={logout}>
            {copy.signOut}
          </button>
        </div>
      </aside>
      {menu && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation backdrop"
          onClick={closeMenu}
        />
      )}
      <section lang="en" className="main" inert={menu ? true : undefined}>
        <ProductionWorkspaceCue authenticated />
        <header className="topbar">
          <button
            ref={toggle}
            className="mobile-toggle"
            aria-label="Toggle conversations"
            onClick={() => setMenu(!menu)}
          >
            ☰
          </button>
          <h1>{list.find((c) => c.id === selected)?.title || "Chat"}</h1>
          {selected && (
            <>
              <button disabled={busy} onClick={rename}>
                Rename
              </button>
              <button disabled={busy} onClick={remove}>
                Delete
              </button>
            </>
          )}
        </header>
        <p className="inference-status" role="status">
          {model ? <>
            {model.real_inference
              ? "Real inference"
              : "Mock inference — no AI model"}
            {" · "}
            {model.backend}
            {" · "}
            {model.model_identifier}
          </> : "Loading inference configuration…"}
        </p>
        <p className="inference-status" role="status">{busy ? (locale === "de" ? "Antwort wird erstellt" : "Generating response") : (messages.length ? (locale === "de" ? "Unterhaltung geladen" : "Conversation loaded") : "")}</p>
        <div className="messages" aria-busy={busy} onScroll={event => {
          const element = event.currentTarget;
          followLatest.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        }}>
          {!messages.length && partial === null && (
            <div className="welcome">
              <p className="eyebrow">YOUR AI WORKSPACE</p>
              <h2>
                What would you like
                <br />
                to explore?
              </h2>
              <p>
                {locale==='de'?'Beginnen Sie mit einer Frage. Für Antworten aus eigenen Dokumenten fügen Sie zunächst unter Knowledge eine Quelle hinzu.':'Start with a question. For answers based on your documents, add a source in Knowledge first.'}
              </p>
              <p><Link href="/knowledge">{locale==='de'?'Eigene Wissensquelle hinzufügen':'Add your first knowledge source'}</Link>{' · '}<a href={documentationUrls.public+'/docs/public/applications'}>{locale==='de'?'Anwendungsleitfaden lesen':'Read the application guide'}</a></p>
              <div className="suggestions">
                {[
                  "Explain a complex idea simply",
                  "Help me plan my next project",
                  "Review a piece of code",
                  "Explore a new perspective",
                ].map((text) => (
                  <button
                    key={text}
                    onClick={() => {
                      setInput(text);
                      entry.current?.focus();
                    }}
                  >
                    {text} ↗
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <article key={m.id} className={`message ${m.role}`}>
              <div className="label">
                {m.role === "user" ? "You" : "Onesa AI"}
              </div>
              <Suspense fallback={<div style={{whiteSpace: "pre-wrap"}}>{m.content.text}</div>}>
                <MessageContent text={m.content.text}/>
              </Suspense>
              {!!m.content.sources?.length && (
                <div className="sources">
                  Sources:{" "}
                  {m.content.sources.map((source, i) => (
                    <Link key={i} href="/knowledge">
                      {source.title}
                    </Link>
                  ))}
                </div>
              )}
              <button
                onClick={() =>
                  navigator.clipboard
                    .writeText(m.content.text)
                    .catch(() => setError("Unable to copy message"))
                }
              >
                Copy message
              </button>
            </article>
          ))}
          {partial !== null && (
            <article className="message">
              <div className="label">
                Onesa AI {busy ? "· Generating" : "· Interrupted"}
              </div>
              <Suspense fallback={<div style={{whiteSpace: "pre-wrap"}}>{partial || "…"}</div>}>
                <MessageContent text={partial || "…"} highlight={false}/>
              </Suspense>
            </article>
          )}
          <div ref={bottom} />
        </div>
        <div className="composer">
          {(!!documents.length || knowledge.error || knowledge.loading) && (
            <details className="document-picker">
              <summary>Use documents ({documentIds.length} selected)</summary>
              <RecordPageControls page={knowledge} />
              {!!documentIds.length && <button type="button" disabled={busy} onClick={() => setDocumentIds([])}>Clear selected documents</button>}
              {documents.map((d) => (
                <label key={d.id}>
                  <input
                    type="checkbox"
                    disabled={busy}
                    checked={documentIds.includes(d.id)}
                    onChange={(e) =>
                      setDocumentIds((ids) =>
                        e.target.checked
                          ? [...ids, d.id]
                          : ids.filter((id) => id !== d.id),
                      )
                    }
                  />
                  {d.title}
                </label>
              ))}
            </details>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <form onSubmit={send} className="input-wrap">
            <textarea
              ref={entry}
              aria-label="Message Onesa AI"
              disabled={!knowledgeReady}
              placeholder="Message Onesa AI…"
              value={input}
              maxLength={32000}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  if (!busy && input.trim())
                    e.currentTarget.form?.requestSubmit();
                }
              }}
            />
            {busy ? (
              <button type="button" disabled={!canStop} onClick={() => void stop()}>
                Stop
              </button>
            ) : (
              <button
                className="send"
                disabled={!input.trim() || !knowledgeReady}
                aria-label="Send message"
              >
                Send ↑
              </button>
            )}
          </form>
          <div className="caption">
            <DocumentationHelp topic="chat" /> · Check important information.
            The selected inference backend is shown above.
          </div>
        </div>
      </section>
    </main>
  );
}
