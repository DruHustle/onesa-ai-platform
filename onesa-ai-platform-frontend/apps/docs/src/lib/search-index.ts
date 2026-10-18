export type SearchEntry = {title: string; url: string; text: string; preview?: string; keywords?: string};
export type IndexedSearchEntry = SearchEntry & {searchTitle: string; searchText: string};

export async function readSearchIndex(response: Response): Promise<SearchEntry[]> {
  if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('Documentation search is unavailable');
  }
  const value: unknown = await response.json();
  if (!Array.isArray(value) || !value.every(entry =>
    entry && typeof entry.title === 'string' && typeof entry.url === 'string' && typeof entry.text === 'string'
    && (entry.preview === undefined || typeof entry.preview === 'string')
    && (entry.keywords === undefined || typeof entry.keywords === 'string')
  )) throw new Error('Documentation search is unavailable');
  return value;
}

export function prepareSearchIndex(entries: SearchEntry[]): IndexedSearchEntry[] {
  return entries.map(({title, url, text, preview, keywords}) => ({
    title, url, text, preview, keywords,
    searchTitle: title.toLowerCase(),
    searchText: (title + ' ' + text + ' ' + (keywords || '')).toLowerCase(),
  }));
}

export function searchDocumentation(entries: IndexedSearchEntry[], query: string): SearchEntry[] {
  const terms = query.toLowerCase().trim().split(/\s+/);
  if (!query.trim()) return [];
  return entries
    .filter(entry => terms.every(term => entry.searchText.includes(term)))
    .map(entry => ({entry, score: terms.reduce((score, term) =>
      score + (entry.searchTitle.includes(term) ? 10 : 1), 0)}))
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)
    .map(({entry}) => entry);
}
