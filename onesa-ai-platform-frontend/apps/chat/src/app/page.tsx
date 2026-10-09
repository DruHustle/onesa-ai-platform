"use client";
import DocumentationNav from "../components/documentation-nav";
import DocumentationHelp from "../components/documentation-help";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

type User = { id: string; display_name: string };
type Conversation = { id: string; title: string };
type Message = {
  id: string;
  role: string;
  content: { text: string; sources?: { document_id: string; title: string }[] };
};
import { call, csrf, api } from "../lib/api";
import Link from "next/link";
import { LanguageSelect, useLocale } from "../lib/i18n";
export default function Chat() {
  const { copy } = useLocale();
  const [model, setModel] = useState<{
    backend: string;
    model_identifier: string;
    real_inference: boolean;
  } | null>(null);
  const [documents, setDocuments] = useState<{ id: string; title: string }[]>(
    [],
  );
  const [documentIds, setDocumentIds] = useState<string[]>([]);
  const [user, setUser] = useState<User | null>(null),
    [checking, setChecking] = useState(true),
    [signup, setSignup] = useState(false);
  const [list, setList] = useState<Conversation[]>([]),
    [selected, setSelected] = useState<string | null>(null),
    [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(""),
    [partial, setPartial] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [menu, setMenu] = useState(false);
  const sidebar = useRef<HTMLElement | null>(null);
  const toggle = useRef<HTMLButtonElement | null>(null);
  const abort = useRef<AbortController | null>(null),
    bottom = useRef<HTMLDivElement | null>(null),
    entry = useRef<HTMLTextAreaElement | null>(null);
  const refreshList = useCallback(async () => {
    const response = await call("/conversations");
    setList((await response.json()).items);
  }, []);
  useEffect(() => {
    let active = true;
    api("GET /auth/me")
      .then((u) => {
        if (active) setUser(u);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
      abort.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (user)
      call("/models")
        .then((r) => r.json())
        .then((data) => setModel(data.items[0]))
        .catch((e) => setError(e.message));
    if (user)
      call("/knowledge/documents")
        .then((r) => r.json())
        .then((data) => {
          setDocuments(data.items);
          const id = new URLSearchParams(window.location.search).get(
            "document",
          );
          if (id && data.items.some((d: { id: string }) => d.id === id))
            setDocumentIds([id]);
        })
        .catch(() => {});
    if (user)
      call("/conversations")
        .then((r) => r.json())
        .then((data) => setList(data.items))
        .catch((e) => setError(e.message));
  }, [user]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
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
      setUser(await response.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function open(id: string) {
    if (busy) return;
    setError("");
    try {
      const r = await call(`/conversations/${id}`);
      setMessages((await r.json()).messages);
      setSelected(id);
      setPartial(null);
      setMenu(false);
      entry.current?.focus();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function create(): Promise<string> {
    const r = await call("/conversations", "POST", {
      title: input.trim().slice(0, 70) || "New conversation",
    });
    const row = await r.json();
    setSelected(row.id);
    setMessages([]);
    await refreshList();
    return row.id;
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim() || busy) return;
    const content = input;
    setBusy(true);
    setError("");
    setInput("");
    let id = selected;
    try {
      if (!id) id = await create();
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
      const reader = response.body?.getReader();
      if (!reader) throw new Error("Streaming unavailable");
      const decoder = new TextDecoder();
      let pending = "",
        ended = false;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        pending += decoder.decode(value, { stream: true });
        let boundary;
        while ((boundary = pending.indexOf("\n\n")) >= 0) {
          const frame = pending.slice(0, boundary);
          pending = pending.slice(boundary + 2);
          const kind = frame
            .split("\n")
            .find((l) => l.startsWith("event:"))
            ?.slice(6)
            .trim();
          const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const data = JSON.parse(dataLine.slice(5));
          if (kind === "content_delta")
            setPartial((p) => (p || "") + data.text);
          if (kind === "error") throw new Error(data.message);
          if (kind === "message_end") {
            ended = true;
            if (data.model) setModel(data.model);
          }
        }
      }
      if (!ended) throw new Error("Response interrupted. You can retry.");
      setPartial(null);
    } catch (e) {
      setError(
        (e as Error).name === "AbortError"
          ? "Generation stopped."
          : (e as Error).message,
      );
    } finally {
      abort.current = null;
      setBusy(false);
      if (id) {
        try {
          const r = await call(`/conversations/${id}`);
          setMessages((await r.json()).messages);
        } catch {
          /* Keep the existing generation error visible if history reload fails. */
        }
      }
      await refreshList().catch(() => {});
      entry.current?.focus();
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
      setSelected(null);
      setMessages([]);
      setPartial(null);
      await refreshList();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function logout() {
    try {
      await call("/auth/logout", "POST");
      setUser(null);
      setMessages([]);
      setSelected(null);
      setList([]);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (checking)
    return (
      <div className="loading" role="status">
        {copy.opening}
      </div>
    );
  if (!user)
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="brand">
            Onesa <span>AI</span>
          </div>
          <h1>{signup ? copy.createTitle : copy.welcome}</h1>
          <p>{copy.description}</p>
          <form onSubmit={authenticate}>
            {signup && (
              <label>
                {copy.name}
                <input
                  name="name"
                  autoComplete="name"
                  required
                  maxLength={80}
                />
              </label>
            )}
            <label>
              {copy.email}
              <input name="email" type="email" autoComplete="email" required />
            </label>
            <label>
              {copy.password}
              <input
                name="password"
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
            <button className="send" disabled={busy}>
              {busy ? copy.wait : signup ? copy.create : copy.signIn}
            </button>
          </form>
          <LanguageSelect />
          <button
            className="switch"
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
          Onesa <span>AI</span>
        </div>
        <div className="feature-nav">
          <Link href="/">{copy.chat}</Link>
          <Link href="/knowledge">{copy.knowledge}</Link>
          <Link href="/agents">{copy.agents}</Link>
          <Link href="/travel">{copy.travel}</Link>
          <DocumentationNav />
        </div>
        <button
          className="new"
          disabled={busy}
          onClick={() => {
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
          {!list.length && (
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
        <header className="topbar">
          <button
            ref={toggle}
            className="mobile-toggle"
            aria-label="Toggle conversations"
            onClick={() => setMenu(!menu)}
          >
            ☰
          </button>
          <h1>{list.find((c) => c.id === selected)?.title || "Onesa Chat"}</h1>
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
        {model && (
          <p className="inference-status" role="status">
            {model.real_inference
              ? "Real local inference"
              : "Mock inference — no AI model"}
            {" · "}
            {model.backend}
            {" · "}
            {model.model_identifier}
          </p>
        )}
        <div className="messages" aria-live="polite">
          {!messages.length && partial === null && (
            <div className="welcome">
              <p className="eyebrow">YOUR AI WORKSPACE</p>
              <h2>
                What would you like
                <br />
                to explore?
              </h2>
              <p>
                Ask a question, work through an idea, or start something new.
              </p>
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
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
              >
                {m.content.text}
              </ReactMarkdown>
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
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {partial || "…"}
              </ReactMarkdown>
            </article>
          )}
          <div ref={bottom} />
        </div>
        <div className="composer">
          {!!documents.length && (
            <details className="document-picker">
              <summary>Use documents ({documentIds.length} selected)</summary>
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
              <button type="button" onClick={() => abort.current?.abort()}>
                Stop
              </button>
            ) : (
              <button
                className="send"
                disabled={!input.trim()}
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
