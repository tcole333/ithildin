import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import type MiniSearch from 'minisearch';
import { getSearchEngine, searchWithRanking, type SearchDocument, type RankedResult } from '../lib/searchEngine';

const TYPE_LABELS: Record<string, string> = {
  dossier: 'Dossier',
  article: 'Article',
  model: 'Model',
};

const TYPE_COLORS: Record<string, string> = {
  dossier: 'var(--color-icy)',
  article: 'var(--color-ember)',
  model: 'var(--color-mithril)',
};

export default function SearchModal() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [engine, setEngine] = useState<MiniSearch<SearchDocument> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const doOpen = useCallback(() => setOpen(true), []);

  const doClose = useCallback(() => {
    setOpen(false);
    setQuery('');
    setActiveIndex(0);
  }, []);

  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    inputRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open || engine) return;
    let active = true;
    setLoading(true);
    setError(null);
    getSearchEngine().then(
      ready => {
        if (active) { setEngine(ready); setLoading(false); }
      },
      () => {
        if (active) { setError('Search could not load. Please try again.'); setLoading(false); }
      },
    );
    return () => { active = false; };
  }, [open, engine, retry]);

  // Cmd+K / Ctrl+K global listener
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (open) doClose();
        else doOpen();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, doOpen, doClose]);

  // CustomEvent from nav button
  useEffect(() => {
    const handler = () => doOpen();
    window.addEventListener('open-search', handler);
    return () => window.removeEventListener('open-search', handler);
  }, [doOpen]);

  const results: RankedResult[] = useMemo(
    () => engine && query.trim() ? searchWithRanking(engine, query) : [],
    [engine, query],
  );

  // Recompute immediately when an index finishes loading after the user types.
  useEffect(() => {
    setActiveIndex(0);
  }, [engine, query]);

  // Scroll active result into view
  useEffect(() => {
    if (!listRef.current) return;
    const active = listRef.current.children[activeIndex] as HTMLElement | undefined;
    active?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  const navigate = (href: string) => {
    doClose();
    window.location.href = href;
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, Math.max(0, results.length - 1)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && results[activeIndex]) {
      e.preventDefault();
      navigate(results[activeIndex].href);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      doClose();
    } else if (e.key === 'Tab') {
      const elements = modalRef.current?.querySelectorAll<HTMLElement>('input, button, a[href], [tabindex="0"]');
      if (!elements?.length) return;
      const first = elements[0];
      const last = elements[elements.length - 1];
      if ((e.shiftKey && document.activeElement === first) || (!e.shiftKey && document.activeElement === last)) {
        e.preventDefault();
        (e.shiftKey ? last : first).focus();
      }
    }
  };

  if (!open) return null;

  return (
    <div className="search-overlay" onClick={doClose}>
      <div ref={modalRef} className="search-modal" role="dialog" aria-modal="true" aria-label="Search content" onClick={e => e.stopPropagation()} onKeyDown={onKeyDown}>
        <div className="search-input-wrap">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-mithril)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="search-input"
            placeholder="Search dossiers, articles, models..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            aria-label="Search dossiers, articles, and models"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={results.length > 0}
            aria-controls="search-result-list"
            aria-activedescendant={results[activeIndex] ? `search-result-${activeIndex}` : undefined}
          />
          <kbd className="search-kbd">ESC</kbd>
        </div>

        <div className="search-results" aria-busy={loading}>
          {loading && (
            <div className="search-empty" role="status">Loading index...</div>
          )}

          {error && <div className="search-empty" role="alert">{error} <button onClick={() => setRetry(value => value + 1)}>Try again</button></div>}

          {!loading && !error && query && results.length === 0 && (
            <div className="search-empty">No results for "{query}"</div>
          )}

          {!loading && !error && !query && (
            <div className="search-empty">Type to search across all content</div>
          )}

          <div ref={listRef} id="search-result-list" role="listbox" aria-label="Search results">{results.map((r, i) => (
            <a
              key={r.id}
              id={`search-result-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              href={r.href}
              className={`search-result ${i === activeIndex ? 'search-result--active' : ''}`}
              onMouseEnter={() => setActiveIndex(i)}
              onClick={e => { e.preventDefault(); navigate(r.href); }}
            >
              <span className="search-result__badge" style={{ borderColor: TYPE_COLORS[r.type], color: TYPE_COLORS[r.type] }}>
                {TYPE_LABELS[r.type]}
              </span>
              <div className="search-result__body">
                <div className="search-result__title">{r.title}</div>
                {r.description && (
                  <div className="search-result__desc">
                    {r.description.length > 120 ? r.description.slice(0, 120) + '...' : r.description}
                  </div>
                )}
              </div>
              {r.tier === 'cross-reference' && r.mentionCount > 0 && (
                <span className="search-result__mentions">{r.mentionCount} conn.</span>
              )}
              {r.stats && r.tier === 'primary' && (
                <span className="search-result__stats">{r.stats}</span>
              )}
            </a>
          ))}</div>
        </div>
      </div>
    </div>
  );
}
