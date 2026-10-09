export type SearchEntry = {title: string; url: string; text: string};

export async function readSearchIndex(response: Response): Promise<SearchEntry[]> {
  if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('Documentation search is unavailable');
  }
  const value: unknown = await response.json();
  if (!Array.isArray(value) || !value.every(entry =>
    entry && typeof entry.title === 'string' && typeof entry.url === 'string' && typeof entry.text === 'string'
  )) throw new Error('Documentation search is unavailable');
  return value;
}
