"use client";
import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useId,
  useMemo,
  useRef,
} from "react";
import { protectDraftHistory } from "../lib/draft-history";
type Draft = {
  dirty: () => boolean;
  pending: () => boolean;
  discard: () => void;
};
function controller() {
  const drafts = new Map<string, Draft>();
  const active = () =>
    [...drafts.values()].some((d) => d.dirty() || d.pending());
  const allow = () => {
    if ([...drafts.values()].some((d) => d.pending())) {
      window.alert(
        "A request is still in progress. Wait for its result before leaving this task.",
      );
      return false;
    }
    if (![...drafts.values()].some((d) => d.dirty())) return true;
    if (
      !window.confirm(
        "You have unsaved changes. Choose Cancel to keep editing, or OK to discard them and leave.",
      )
    )
      return false;
    for (const d of drafts.values()) if (d.dirty()) d.discard();
    return true;
  };
  return {
    active,
    allow,
    register(id: string, draft: Draft) {
      drafts.set(id, draft);
      return () => {
        drafts.delete(id);
      };
    },
  };
}
const Context = createContext<ReturnType<typeof controller> | null>(null);
export function DraftNavigationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const guard = useMemo(() => controller(), []);
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (guard.active()) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    const click = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const anchor =
        event.target instanceof Element
          ? event.target.closest("a[href]")
          : null;
      if (
        !(anchor instanceof HTMLAnchorElement) ||
        anchor.target === "_blank" ||
        anchor.hasAttribute("download") ||
        !/^https?:$/.test(anchor.protocol)
      )
        return;
      if (guard.active() && !guard.allow()) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    };
    const cleanup = protectDraftHistory(guard.allow);
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", click, true);
    return () => {
      cleanup();
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", click, true);
    };
  }, [guard]);
  return <Context.Provider value={guard}>{children}</Context.Provider>;
}
/** Values remain in this mounted workspace only, never in browser storage. */
export function useDraftNavigation(
  dirty: boolean,
  pending: boolean,
  discard: () => void,
) {
  const guard = useContext(Context),
    id = useId(),
    latest = useRef({ dirty, pending, discard });
  useLayoutEffect(() => {
    latest.current = { dirty, pending, discard };
  }, [dirty, pending, discard]);
  if (!guard) throw new Error("Draft navigation provider is required");
  useEffect(
    () =>
      guard.register(id, {
        dirty: () => latest.current.dirty,
        pending: () => latest.current.pending,
        discard: () => latest.current.discard(),
      }),
    [guard, id],
  );
  return (action: () => void) => {
    if (guard.allow()) action();
  };
}
