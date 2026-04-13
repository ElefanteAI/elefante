// Elefante Dashboard v2.4.0 - Search Hook
import { useState, useCallback, useRef } from 'react';
import type { SearchResult } from '@/types';

interface UseSearchReturn {
  results: SearchResult[];
  isSearching: boolean;
  searchError: string | null;
  search: (query: string) => Promise<void>;
  clear: () => void;
}

export function useSearch(): UseSearchReturn {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const search = useCallback(async (query: string) => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    // Abort previous request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsSearching(true);
    setSearchError(null);

    try {
      const res = await fetch(
        `/api/search?query=${encodeURIComponent(query)}&limit=20&min_similarity=0.3`,
        { signal: controller.signal }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (!data.success) throw new Error(data.error || 'Search failed');

      setResults(data.results || []);
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setSearchError(e.message);
        setResults([]);
      }
    } finally {
      setIsSearching(false);
    }
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setResults([]);
    setSearchError(null);
  }, []);

  return { results, isSearching, searchError, search, clear };
}
