import { useCallback, useEffect, useRef, useState } from 'react';
import { listCompanies } from '../../services/companies';
import type { Company } from '../../types';

interface State {
  companies: Company[];
  loading: boolean;
  error: string | null;
}

/**
 * Loads companies from the API, re-querying when the search term changes.
 *
 * Search runs server-side so the list stays correct once it is longer than one
 * page. Requests are debounced and stale responses are discarded.
 */
export function useCompanies(search: string) {
  const [state, setState] = useState<State>({ companies: [], loading: true, error: null });
  const requestId = useRef(0);

  const load = useCallback(async (term: string) => {
    const id = ++requestId.current;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const page = await listCompanies(term);
      if (id === requestId.current) {
        setState({ companies: page.items, loading: false, error: null });
      }
    } catch (caught) {
      if (id === requestId.current) {
        setState({
          companies: [],
          loading: false,
          error: caught instanceof Error ? caught.message : 'Request failed',
        });
      }
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void load(search), search ? 250 : 0);
    return () => clearTimeout(timer);
  }, [search, load]);

  const refresh = useCallback(() => load(search), [load, search]);

  /** Insert or replace a company in local list without duplicating (e.g. after create). */
  const upsertCompany = useCallback((company: Company) => {
    setState((previous) => {
      const without = previous.companies.filter((entry) => entry.id !== company.id);
      return {
        ...previous,
        companies: [company, ...without],
        loading: false,
        error: null,
      };
    });
  }, []);

  return { ...state, refresh, upsertCompany };
}
