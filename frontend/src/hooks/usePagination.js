import { useCallback, useState } from 'react';

/** Page/page-size state plus filter state that resets the page when changed. */
export function usePagination(initialFilters = {}, { pageSize: initialPageSize = 25 } = {}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const [filters, setFiltersState] = useState(initialFilters);

  const setFilter = useCallback((key, value) => {
    setFiltersState((f) => ({ ...f, [key]: value }));
    setPage(1);
  }, []);

  const setFilters = useCallback((next) => {
    setFiltersState(next);
    setPage(1);
  }, []);

  const setPageSize = useCallback((size) => {
    setPageSizeState(size);
    setPage(1);
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(initialFilters);
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    page, setPage, pageSize, setPageSize, filters, setFilter, setFilters, resetFilters,
    params: { ...filters, page, page_size: pageSize },
  };
}
