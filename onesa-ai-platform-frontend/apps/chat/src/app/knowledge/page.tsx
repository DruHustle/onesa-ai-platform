"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import FeatureShell from "../../components/feature-shell";
import { uploadDocument } from "../../lib/uploads";
import {
  api,
  type DocumentMetadata as Document,
  type DocumentDetail,
  type KnowledgeSource as Source,
} from "../../lib/api";
export default function Knowledge() {
  const [documents, setDocuments] = useState<Document[]>([]),
    [sources, setSources] = useState<Source[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [query, setQuery] = useState("");
  const [preview, setPreview] = useState<DocumentDetail | null>(null);
  const [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    const response = await api("GET /knowledge/documents");
    setDocuments(response.items);
  }, []);
  useEffect(() => {
    api("GET /knowledge/documents")
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
        throw new Error(
          `Maximum file size is ${Math.floor(limit / 1048576)} MB`,
        );
      }
      await uploadDocument(data);
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
      const response = await api("POST /knowledge/search", {
        body: { query, limit: 5 },
      });
      setSources(response.sources);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: string) {
    if (!window.confirm("Delete this document and its search index?")) return;
    try {
      await api("DELETE /knowledge/documents/{identifier}", {
        params: { identifier: id },
      });
      setSources([]);
      if (preview?.id === id) setPreview(null);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function inspect(id: string) {
    setBusy(true);
    setError("");
    try {
      setPreview(
        await api("GET /knowledge/documents/{identifier}", {
          params: { identifier: id },
        }),
      );
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reindex(id: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("POST /knowledge/documents/{identifier}/reindex", {
        params: { identifier: id },
      });
      setSources([]);
      if (preview?.id === id) setPreview(null);
      await load();
      setNotice(
        "Document search index rebuilt using the configured embedding service.",
      );
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <FeatureShell title="Your knowledge">
      <p className="intro">
        Bring your documents into the conversation. Upload a text file or a
        text-based PDF, then search or ask Onesa about it.
      </p>
      <p role="status" aria-live="polite">
        {notice}
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
            <button disabled={busy} onClick={() => inspect(d.id)}>
              Preview extracted text
            </button>
            <button disabled={busy} onClick={() => reindex(d.id)}>
              Rebuild search index
            </button>
            <button disabled={busy} onClick={() => remove(d.id)}>
              Delete document
            </button>
          </article>
        ))}
        {!documents.length && <p>No documents yet.</p>}
      </div>
      {preview && (
        <section className="feature-card" aria-labelledby="preview-heading">
          <h2 id="preview-heading">Preview: {preview.title}</h2>
          <p>
            Extracted text, showing the first 12,000 characters. This preview
            does not display the original PDF layout.
          </p>
          <p className="excerpt">{preview.text.slice(0, 12000)}</p>
          <button onClick={() => setPreview(null)}>Close preview</button>
        </section>
      )}
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
