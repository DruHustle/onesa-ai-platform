"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import FeatureShell from "../../components/feature-shell";
import { call, csrf } from "../../lib/api";
type Document = { id: string; title: string; embedding_version: string };
type Source = {
  document_id: string;
  title: string;
  text: string;
  chunk: number;
};
export default function Knowledge() {
  const [documents, setDocuments] = useState<Document[]>([]),
    [sources, setSources] = useState<Source[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [query, setQuery] = useState("");
  const load = useCallback(async () => {
    const response = await call("/knowledge/documents");
    setDocuments((await response.json()).items);
  }, []);
  useEffect(() => {
    call("/knowledge/documents")
      .then((r) => r.json())
      .then((r) => setDocuments(r.items))
      .catch((e) => setError(e.message));
  }, []);
  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    setError("");
    try {
      const data = new FormData(form);
      const file = data.get("file");
      const limit = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_BYTES || 5242880);
      if (file instanceof File && file.size > limit) {
        throw new Error(`Maximum file size is ${Math.floor(limit / 1048576)} MB`);
      }
      const response = await fetch("/api/v1/knowledge/documents", {
        method: "POST",
        headers: { "X-CSRF-Token": csrf() },
        body: data,
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error?.message || "Upload failed");
      }
      form.reset();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function search(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await call("/knowledge/search", "POST", { query });
      setSources((await response.json()).sources);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: string) {
    if (!window.confirm("Delete this document and its search index?")) return;
    try {
      await call(`/knowledge/documents/${id}`, "DELETE");
      setSources([]);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <FeatureShell title="Your knowledge">
      <p className="intro">
        Bring your documents into the conversation. Upload a text file or a
        text-based PDF, then search or ask Onesa about it.
      </p>
      {error && (
        <div className="error" role="alert">
          {error} <Link href="/">Return to Chat to sign in.</Link>
        </div>
      )}
      <form onSubmit={upload} className="feature-card">
        <label>
          Document (.txt or .pdf, up to 5 MiB)
          <input type="file" name="file" accept=".txt,.pdf" required />
        </label>
        <button className="send" disabled={busy}>
          Upload document
        </button>
      </form>
      <h2>Documents</h2>
      <div className="document-list">
        {documents.map((d) => (
          <article className="feature-card" key={d.id}>
            <strong>{d.title}</strong>
            <p>
              {d.embedding_version.startsWith("lexical:")
                ? "Lexical retrieval baseline"
                : "Configured embedding model"}
            </p>
            <Link href={`/?document=${d.id}`}>Ask about this document →</Link>
            <button onClick={() => remove(d.id)}>Delete document</button>
          </article>
        ))}
        {!documents.length && <p>No documents yet.</p>}
      </div>
      <form onSubmit={search} className="search-form">
        <label>
          Search your documents
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            required
            maxLength={4000}
          />
        </label>
        <button disabled={busy} className="send">
          Search
        </button>
      </form>
      {sources.map((s) => (
        <article className="feature-card" key={`${s.document_id}:${s.chunk}`}>
          <strong>
            {s.title} · excerpt {s.chunk + 1}
          </strong>
          <p className="excerpt">{s.text}</p>
        </article>
      ))}
    </FeatureShell>
  );
}
