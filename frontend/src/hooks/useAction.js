import { useCallback, useRef, useState } from 'react';
import { useToast } from '../components/Toast';
import { errorMessage } from '../api/client';

/**
 * Run a named mutation: tracks which action is pending (to disable its button),
 * shows a success toast only after a 2xx response, and an error toast otherwise.
 */
export function useAction() {
  const toast = useToast();
  const [pending, setPending] = useState(null);
  const busy = useRef(false);

  const run = useCallback(async (key, fn, { success, onSuccess, toastError = true } = {}) => {
    if (busy.current) return { ok: false, error: new Error('Another action is in progress') };
    busy.current = true;
    setPending(key);
    try {
      const data = await fn();
      if (success) toast.success(typeof success === 'function' ? success(data) : success);
      if (onSuccess) await onSuccess(data);
      return { ok: true, data };
    } catch (error) {
      if (toastError) toast.error(errorMessage(error));
      return { ok: false, error };
    } finally {
      busy.current = false;
      setPending(null);
    }
  }, [toast]);

  return { run, pending, isPending: (key) => pending === key, anyPending: pending !== null };
}
