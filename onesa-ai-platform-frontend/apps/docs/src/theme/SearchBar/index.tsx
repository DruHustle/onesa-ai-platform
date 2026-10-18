import React, {useCallback, useEffect, useId, useMemo, useRef, useState} from 'react';
import Link from '@docusaurus/Link';
import {prepareSearchIndex, readSearchIndex, searchDocumentation,
  type IndexedSearchEntry} from '../../lib/search-index';

export default function Search() {
  const [query, setQuery] = useState('');
  const [entries, setEntries] = useState<IndexedSearchEntry[]>([]);
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');
  const box = useRef<HTMLInputElement>(null);
  const results = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);
  const deadline = useRef<number | null>(null);
  const load = useRef<Promise<void> | null>(null);
  const resultsId = useId();

  const activate = useCallback(() => {
    setOpen(true);
    if (load.current) return;
    const request = new AbortController();
    controller.current = request;
    deadline.current = window.setTimeout(() => request.abort(), 10000);
    setState('loading');
    // Keep this cache inside the mounted search: no stored or cross-session private index.
    load.current = fetch('/generated/search.json', {signal: request.signal, credentials: 'same-origin'})
      .then(readSearchIndex)
      .then(prepareSearchIndex)
      .then(index => {
        if (controller.current === request && !request.signal.aborted) {setEntries(index); setState('ready');}
      })
      .catch(() => {
        if (controller.current === request) {setEntries([]); setState('unavailable');}
      })
      .finally(() => {
        if (deadline.current !== null) window.clearTimeout(deadline.current);
        deadline.current = null;
        controller.current = null;
      });
  }, []);

  useEffect(() => {
    // Adopt real input made before hydration; keep an idle reader's index deferred.
    const input = box.current;
    if (input) {
      setQuery(input.value);
      if (document.activeElement === input) activate();
    }
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        box.current?.focus();
        activate();
      }
      if (event.key === 'Escape') {
        if (results.current?.contains(document.activeElement)) box.current?.focus();
        setOpen(false);
      }
    };
    document.addEventListener('keydown', key);
    return () => {
      const request = controller.current;
      controller.current = null;
      request?.abort();
      if (deadline.current !== null) window.clearTimeout(deadline.current);
      deadline.current = null;
      document.removeEventListener('keydown', key);
    };
  }, [activate]);

  const matches = useMemo(() => searchDocumentation(entries, query), [entries, query]);
  return <div className="global-search">
    <input ref={box} aria-label="Search documentation" placeholder="Search docs… ⌘K"
      aria-controls={open ? resultsId : undefined} defaultValue="" onFocus={activate}
      onChange={event => {setQuery(event.target.value); activate();}}
      onKeyDown={event => {
        if (event.key === 'Enter' && matches[0]) window.location.assign(matches[0].url);
      }}/>
    {open && <div ref={results} id={resultsId} className="search-results" role="region"
      aria-label="Search results" aria-busy={state === 'loading'}>
      <button type="button" className="search-close" aria-label="Close search" onClick={() => {
        box.current?.focus(); setOpen(false);
      }}>×</button>
      {state === 'loading' && <p role="status">Loading documentation search…</p>}
      {state === 'unavailable' && <p role="alert">Documentation search is unavailable. Sign in again or reload.</p>}
      {state === 'ready' && matches.map(entry => <Link key={entry.title + entry.url} to={entry.url}
        onClick={() => setOpen(false)}><strong>{entry.title}</strong>
        <small>{entry.preview ?? entry.text.replace(/\s+/g, ' ').slice(0, 150) + '…'}</small></Link>)}
      {state === 'ready' && !matches.length && <p>{query.trim() ? 'No matching documents.' : 'Type to search documentation.'}</p>}
    </div>}
  </div>;
}
