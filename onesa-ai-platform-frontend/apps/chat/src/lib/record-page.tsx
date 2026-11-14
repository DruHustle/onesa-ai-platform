"use client";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type SetStateAction } from "react";
import { call } from "./api";

const subscribe = (changed: () => void) => {
  window.addEventListener("popstate", changed);
  window.addEventListener("onesa-record-page", changed);
  return () => {window.removeEventListener("popstate", changed); window.removeEventListener("onesa-record-page", changed);};
};
const snapshot = () => window.location.search;
const serverSnapshot = () => "";

export function useRecordSelection(parameter: string): [string | null, (value: string | null) => void] {
  const search = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  return [new URLSearchParams(search).get(parameter), value => {
    const url = new URL(window.location.href);
    if (value) url.searchParams.set(parameter, value); else url.searchParams.delete(parameter);
    window.history.replaceState(window.history.state, "", url);
    window.dispatchEvent(new Event("onesa-record-page"));
  }];
}

/** One bounded page in memory; URL cursors survive reload and browser Back. */
export function useRecordPage<T extends { id: string }>(path: string, identity = "session", subject = "history") {
  const search = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  const cursor = new URLSearchParams(search).get(`page_${path.split("/").pop()}`);
  const [attempt, setAttempt] = useState(0);
  const key = `${identity}|${path}|${cursor || ""}|${attempt}`;
  const [result, setResult] = useState<{key: string; items: T[]; nextCursor: string | null; error: string}>(
    {key: "", items: [], nextCursor: null, error: ""});
  const pending = useRef(false);
  const loading = Boolean(identity) && result.key !== key;
  const reload = useCallback(() => setAttempt(value => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    if (!identity) return () => controller.abort();
    pending.current = true;
    const query = new URLSearchParams({limit: "50", ...(cursor ? {cursor} : {})});
    call(`${path}?${query}`, "GET", undefined,
      AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]))
      .then(response => response.json())
      .then((value: {items: T[]; next_cursor?: string | null}) => {
        if (controller.signal.aborted) return;
        setResult(previous => ({key,
          items: Array.from(new Map([...value.items, ...(previous.key === key ? previous.items : [])]
            .map(item => [item.id, item])).values()).slice(0, 50),
          nextCursor: value.next_cursor || null, error: ""}));
      })
      .catch(() => { if (!controller.signal.aborted) setResult({key, items: [], nextCursor: null,
        error: `${subject[0].toUpperCase() + subject.slice(1)} is unavailable. Retry this page or return to the first page.`}); })
      .finally(() => { if (!controller.signal.aborted) pending.current = false; });
    return () => controller.abort();
  }, [identity, key, cursor, path, subject]);
  function go(value: string | null) {
    if (pending.current) return;
    pending.current = true;
    const url = new URL(window.location.href), parameter = `page_${path.split("/").pop()}`;
    if (value) url.searchParams.set(parameter, value); else url.searchParams.delete(parameter);
    window.history.pushState(window.history.state, "", url);
    window.dispatchEvent(new Event("onesa-record-page"));
  }
  const setItems = (value: SetStateAction<T[]>) => setResult(previous => {
    const current = previous.key === key ? previous.items : [];
    return {...previous, key, items: (typeof value === "function" ? value(current) : value).slice(0, 50)};
  });
  const visible = result.key === key && Boolean(identity);
  return {items: visible ? result.items : [], setItems, loading, error: visible ? result.error : "",
    cursor, nextCursor: visible ? result.nextCursor : null, reload,
    next: () => {if (result.nextCursor) go(result.nextCursor);}, first: () => go(null)};
}

export function RecordPageControls({page, subject = "records"}: {subject?: string; page: {
  loading: boolean; error: string; cursor: string | null; nextCursor: string | null;
  reload: () => void; first: () => void; next: () => void;
}}) {
  return <div role="group" aria-label="Record pages">
    {page.loading && <p role="status">Loading {subject}…</p>}
    {page.error && <p role="alert">{page.error} <button onClick={page.reload}>Retry history</button></p>}
    {page.cursor && <button disabled={page.loading} onClick={page.first}>First page</button>}
    {page.nextCursor && <button disabled={page.loading} onClick={page.next}>Older records</button>}
  </div>;
}
