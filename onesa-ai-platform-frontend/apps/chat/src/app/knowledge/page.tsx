"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRecordPage, RecordPageControls } from "../../lib/record-page";
import RequireSession from "../../components/require-session";
import FeatureShell from "../../components/feature-shell";
import { uploadDocument } from "../../lib/uploads";
import {
  api,
  type DocumentMetadata as Document,
  type DocumentDetail,
  type KnowledgeSource as Source,
} from "../../lib/api";
import styles from "./knowledge.module.css";

type SearchState =
  | { status: "idle" | "cleared" }
  | { status: "pending"; query: string }
  | { status: "complete"; query: string; sources: Source[] }
  | { status: "error"; query: string; message: string };
type Mutation = {
  kind: "upload" | "delete" | "reindex";
  title: string;
  id?: string;
};
type PendingMutation = Mutation & { controller: AbortController };
type PendingPreview = {
  id: string;
  title: string;
  controller: AbortController;
};
const errorMessage = (reason: unknown) =>
  reason instanceof Error
    ? reason.message
    : "The request could not be completed. Try again.";

export default function Knowledge() {
  return (
    <RequireSession destination="/knowledge" title="Your knowledge">
      <KnowledgeWorkspace />
    </RequireSession>
  );
}

function KnowledgeWorkspace() {
  const page = useRecordPage<Document>(
    "/knowledge/documents",
    "session",
    "documents",
  );
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchState>({ status: "idle" });
  const searchRequest = useRef<AbortController | null>(null);
  const [mutation, setMutation] = useState<Mutation | null>(null);
  const mutationRequest = useRef<PendingMutation | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<DocumentDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const [previewError, setPreviewError] = useState("");
  const previewRequest = useRef<PendingPreview | null>(null);
  const previewTrigger = useRef<HTMLButtonElement | null>(null);
  const documentsHeading = useRef<HTMLHeadingElement | null>(null);

  useEffect(
    () => () => {
      searchRequest.current?.abort();
      searchRequest.current = null;
      previewRequest.current?.controller.abort();
      previewRequest.current = null;
      mutationRequest.current?.controller.abort();
      mutationRequest.current = null;
    },
    [],
  );

  function clearPreview() {
    previewRequest.current?.controller.abort();
    previewRequest.current = null;
    setPreview(null);
    setPreviewLoading(null);
    setPreviewError("");
  }

  function beginMutation(action: Mutation) {
    if (mutationRequest.current) return null;
    const pending = { ...action, controller: new AbortController() };
    mutationRequest.current = pending;
    setMutation(action);
    setError("");
    setNotice("");
    // A document change invalidates both completed and still-pending read results.
    searchRequest.current?.abort();
    searchRequest.current = null;
    setSearch((current) =>
      current.status === "idle" ? current : { status: "cleared" },
    );
    clearPreview();
    previewTrigger.current = null;
    return pending;
  }

  function isCurrentMutation(pending: PendingMutation): boolean {
    return mutationRequest.current === pending;
  }

  function finishMutation(pending: PendingMutation) {
    if (!isCurrentMutation(pending)) return;
    mutationRequest.current = null;
    setMutation(null);
  }

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutationRequest.current) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get("file");
    const pending = beginMutation({
      kind: "upload",
      title: file instanceof File ? file.name : "document",
    });
    if (!pending) return;
    try {
      const limit = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_BYTES || 5242880);
      if (file instanceof File && file.size > limit) {
        throw new Error(
          `Maximum file size is ${Math.floor(limit / 1048576)} MiB`,
        );
      }
      await uploadDocument(data, pending.controller.signal);
      if (!isCurrentMutation(pending)) return;
      form.reset();
      setNotice(
        `Uploaded “${pending.title}”. You can now search it or ask about it in Chat.`,
      );
      page.reload();
    } catch (reason) {
      if (isCurrentMutation(pending)) setError(errorMessage(reason));
    } finally {
      finishMutation(pending);
    }
  }

  async function searchDocuments(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (searchRequest.current || mutationRequest.current) return;
    const submitted = query.trim();
    if (!submitted) return;
    const pending = new AbortController();
    searchRequest.current = pending;
    // Results always belong to this immutable submitted query, never to a later draft.
    setSearch({ status: "pending", query: submitted });
    try {
      const response = await api("POST /knowledge/search", {
        body: { query: submitted, limit: 5 },
        signal: pending.signal,
      });
      if (searchRequest.current === pending) {
        setSearch({
          status: "complete",
          query: submitted,
          sources: response.sources,
        });
      }
    } catch (reason) {
      if (searchRequest.current === pending) {
        setSearch({
          status: "error",
          query: submitted,
          message: errorMessage(reason),
        });
      }
    } finally {
      if (searchRequest.current === pending) searchRequest.current = null;
    }
  }

  async function remove(document: Document, trigger: HTMLButtonElement) {
    if (
      mutationRequest.current ||
      !window.confirm("Delete this document and its search index?")
    )
      return;
    const pending = beginMutation({
      kind: "delete",
      id: document.id,
      title: document.title,
    });
    if (!pending) return;
    try {
      await api("DELETE /knowledge/documents/{identifier}", {
        params: { identifier: document.id },
        signal: pending.controller.signal,
      });
      if (!isCurrentMutation(pending)) return;
      page.setItems((items) => items.filter((item) => item.id !== document.id));
      page.reload();
      setNotice(`Deleted “${document.title}” and its search index.`);
      if (
        window.document.activeElement === trigger ||
        window.document.activeElement === window.document.body
      ) {
        documentsHeading.current?.focus({ preventScroll: true });
      }
    } catch (reason) {
      if (isCurrentMutation(pending)) setError(errorMessage(reason));
    } finally {
      finishMutation(pending);
    }
  }

  async function inspect(document: Document, trigger: HTMLButtonElement) {
    if (mutationRequest.current || previewRequest.current?.id === document.id)
      return;
    clearPreview();
    const pending = {
      id: document.id,
      title: document.title,
      controller: new AbortController(),
    };
    previewRequest.current = pending;
    previewTrigger.current = trigger;
    setPreviewLoading({ id: document.id, title: document.title });
    try {
      const detail = await api("GET /knowledge/documents/{identifier}", {
        params: { identifier: document.id },
        signal: pending.controller.signal,
      });
      if (previewRequest.current === pending) setPreview(detail);
    } catch (reason) {
      if (previewRequest.current === pending)
        setPreviewError(errorMessage(reason));
    } finally {
      if (previewRequest.current === pending) {
        previewRequest.current = null;
        setPreviewLoading(null);
      }
    }
  }

  async function reindex(document: Document) {
    const pending = beginMutation({
      kind: "reindex",
      id: document.id,
      title: document.title,
    });
    if (!pending) return;
    try {
      await api("POST /knowledge/documents/{identifier}/reindex", {
        params: { identifier: document.id },
        signal: pending.controller.signal,
      });
      if (!isCurrentMutation(pending)) return;
      page.reload();
      setNotice(
        `Document search index rebuilt using the configured embedding service: “${document.title}”.`,
      );
    } catch (reason) {
      if (isCurrentMutation(pending)) setError(errorMessage(reason));
    } finally {
      finishMutation(pending);
    }
  }

  const pendingLabel =
    mutation?.kind === "upload"
      ? `Uploading “${mutation.title}”…`
      : mutation?.kind === "delete"
        ? `Deleting “${mutation.title}”…`
        : mutation
          ? `Rebuilding the search index for “${mutation.title}”…`
          : "";

  return (
    <FeatureShell title="Your knowledge">
      <div className={styles.workspace}>
        <p className={`intro ${styles.intro}`}>
          Bring your documents into the conversation. Add a source, find a
          useful passage, or ask Onesa about it in Chat.
        </p>
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className={styles.liveStatus}
        >
          {(pendingLabel || notice) && (
            <p
              className={`${styles.feedback} ${mutation ? styles.pending : styles.success}`}
            >
              {pendingLabel || notice}
            </p>
          )}
        </div>
        {error && (
          <p className={`error ${styles.feedback}`} role="alert">
            {error} Your file selection and search text are kept so you can try
            again.
          </p>
        )}

        <div className={styles.tools}>
          <form
            onSubmit={upload}
            className={styles.panel}
            aria-labelledby="upload-heading"
            aria-busy={mutation?.kind === "upload"}
          >
            <h2 id="upload-heading">Add a document</h2>
            <p className={styles.supporting}>
              Choose a text file or a text-based PDF. Scanned pages need
              selectable text before upload.
            </p>
            <label className={styles.label} htmlFor="knowledge-upload">
              Document (.txt or .pdf, up to 5 MiB)
            </label>
            <input
              id="knowledge-upload"
              className={styles.fileInput}
              type="file"
              name="file"
              accept=".txt,.pdf"
              required
              disabled={Boolean(mutation)}
              onChange={() => {
                setError("");
                setNotice("");
              }}
            />
            <button className="send" disabled={Boolean(mutation)}>
              {mutation?.kind === "upload"
                ? "Uploading document…"
                : "Upload document"}
            </button>
          </form>
          <section className={styles.panel} aria-labelledby="search-heading">
            <h2 id="search-heading">Find a passage</h2>
            <p className={styles.supporting}>
              Search the documents in your account. Results show the source and
              its extracted text.
            </p>
            <form
              onSubmit={searchDocuments}
              className={styles.searchForm}
              aria-busy={search.status === "pending"}
            >
              <label className={styles.label} htmlFor="knowledge-query">
                Search your documents
              </label>
              <input
                id="knowledge-query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                required
                maxLength={4000}
                placeholder="Ask a question or enter a few keywords"
              />
              <button
                disabled={
                  !query.trim() ||
                  search.status === "pending" ||
                  Boolean(mutation)
                }
                className="send"
              >
                {search.status === "pending" ? "Searching…" : "Search"}
              </button>
            </form>
            <div
              role="status"
              aria-live="polite"
              aria-atomic="true"
              className={`${styles.searchStatus} ${styles.liveStatus}`}
            >
              {search.status === "idle" && (
                <p>Choose a question to search your uploaded sources.</p>
              )}
              {search.status === "pending" && (
                <p>Searching for “{search.query}”…</p>
              )}
              {search.status === "cleared" && (
                <p>
                  Previous search results were cleared for the document action.
                  Search again to use the current documents.
                </p>
              )}
              {search.status === "complete" &&
                (search.sources.length ? (
                  <p>
                    {search.sources.length}{" "}
                    {search.sources.length === 1 ? "passage" : "passages"} found
                    for “{search.query}”.
                  </p>
                ) : (
                  <p>
                    No passages found for “{search.query}”. Try different words
                    or check that the relevant document has been uploaded.
                  </p>
                ))}
            </div>
            {search.status === "error" && (
              <p className={`error ${styles.feedback}`} role="alert">
                Search for “{search.query}” failed. {search.message} Your search
                text is kept; you can try again.
              </p>
            )}
          </section>
        </div>

        {search.status === "complete" && search.sources.length > 0 && (
          <section className={styles.results} aria-labelledby="results-heading">
            <h2 id="results-heading">Search results for “{search.query}”</h2>
            {search.sources.map((source) => (
              <article
                className={styles.panel}
                key={`${source.document_id}:${source.chunk}`}
              >
                <h3>
                  {source.title} · excerpt {source.chunk + 1}
                </h3>
                <p className={styles.excerpt}>{source.text}</p>
              </article>
            ))}
          </section>
        )}

        <section
          className={styles.documents}
          aria-labelledby="documents-heading"
        >
          <div className={styles.sectionHeading}>
            <h2 ref={documentsHeading} id="documents-heading" tabIndex={-1}>
              Documents
            </h2>
            {!page.loading && !page.error && page.items.length > 0 && (
              <p className={styles.supporting}>
                {page.items.length} on this page
              </p>
            )}
          </div>
          {(page.loading || page.error || page.cursor || page.nextCursor) && (
            <RecordPageControls page={page} subject="documents" />
          )}
          {page.items.length > 0 && (
            <div className={styles.documentList}>
              {page.items.map((document) => (
                <article className={styles.panel} key={document.id}>
                  <h3>{document.title}</h3>
                  <p className={styles.supporting}>
                    {document.embedding_version.startsWith("lexical:")
                      ? "Lexical retrieval baseline"
                      : "Configured embedding model"}
                  </p>
                  <Link
                    className={styles.documentLink}
                    href={`/?document=${document.id}`}
                  >
                    Ask about this document →
                  </Link>
                  <div className={styles.actions}>
                    <button
                      disabled={
                        Boolean(mutation) || previewLoading?.id === document.id
                      }
                      onClick={(event) =>
                        void inspect(document, event.currentTarget)
                      }
                    >
                      {previewLoading?.id === document.id
                        ? "Loading preview…"
                        : "Preview extracted text"}
                    </button>
                    <button
                      disabled={Boolean(mutation)}
                      onClick={() => void reindex(document)}
                    >
                      {mutation?.kind === "reindex" &&
                      mutation.id === document.id
                        ? "Rebuilding search index…"
                        : "Rebuild search index"}
                    </button>
                    <button
                      className={styles.delete}
                      disabled={Boolean(mutation)}
                      onClick={(event) =>
                        void remove(document, event.currentTarget)
                      }
                    >
                      {mutation?.kind === "delete" &&
                      mutation.id === document.id
                        ? "Deleting document…"
                        : "Delete document"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
          {!page.loading && !page.error && !page.items.length && (
            <div className={styles.empty}>
              <h3>
                {page.cursor
                  ? "No documents on this page."
                  : "No documents yet."}
              </h3>
              <p>
                {page.cursor
                  ? "Return to the first page to see your current sources."
                  : "Start with a useful note, guide or text-based PDF. Once uploaded, you can search its passages and use it in Chat."}
              </p>
              {!page.cursor && (
                <a className={styles.documentLink} href="#knowledge-upload">
                  Choose your first document
                </a>
              )}
            </div>
          )}
        </section>

        {(preview || previewLoading || previewError) && (
          <section
            className={styles.panel}
            aria-labelledby="preview-heading"
            aria-busy={Boolean(previewLoading)}
          >
            <h2 id="preview-heading">
              {preview
                ? `Preview: ${preview.title}`
                : previewLoading
                  ? `Preview: ${previewLoading.title}`
                  : "Document preview"}
            </h2>
            {previewLoading && <p role="status">Loading extracted text…</p>}
            {previewError && (
              <p className="error" role="alert">
                {previewError} Close the preview and try again.
              </p>
            )}
            {preview && (
              <>
                <p className={styles.supporting}>
                  Extracted text, showing the first 12,000 characters. This
                  preview does not display the original PDF layout.
                </p>
                <p className={styles.excerpt}>{preview.text.slice(0, 12000)}</p>
              </>
            )}
            <div className={styles.actions}>
              <button
                onClick={() => {
                  const trigger = previewTrigger.current;
                  clearPreview();
                  requestAnimationFrame(() => {
                    if (trigger?.isConnected) trigger.focus();
                  });
                }}
              >
                Close preview
              </button>
            </div>
          </section>
        )}
      </div>
    </FeatureShell>
  );
}
