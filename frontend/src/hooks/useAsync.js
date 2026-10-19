import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Run an async loader and track {data, error, loading}.
 * The loader re-runs whenever `deps` change; call `reload()` after mutations.
 */
export function useAsync(loader, deps = [], { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const seq = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const run = useCallback(async () => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await loaderRef.current();
      if (id === seq.current) setState({ data, error: null, loading: false });
      return data;
    } catch (error) {
      if (id === seq.current) setState((s) => ({ ...s, error, loading: false }));
      return undefined;
    }
  }, []);

  useEffect(() => {
    if (enabled) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  const setData = useCallback((updater) => {
    setState((s) => ({ ...s, data: typeof updater === 'function' ? updater(s.data) : updater }));
  }, []);

  return { ...state, reload: run, setData };
}

/**
 * Wrap a mutation: tracks `pending` so buttons can be disabled, and
 * returns {ok, data} or {ok:false, error} without throwing.
 */
export function useMutation(fn) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(async (...args) => {
    setPending(true);
    setError(null);
    try {
      const data = await fnRef.current(...args);
      return { ok: true, data };
    } catch (e) {
      if (mounted.current) setError(e);
      return { ok: false, error: e };
    } finally {
      if (mounted.current) setPending(false);
    }
  }, []);

  return { run, pending, error, setError };
}
