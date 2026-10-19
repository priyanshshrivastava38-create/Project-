import { useCallback, useRef } from 'react';

function uuid() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/**
 * One Idempotency-Key per logical form submission. Re-submitting the identical
 * payload after a failure (e.g. a dropped connection) reuses the key so the
 * server can't record the operation twice; any change to the payload, or a
 * completed submission, produces a fresh key.
 */
export function useIdempotencyKey() {
  const ref = useRef(null);
  const keyFor = useCallback((payload) => {
    const sig = JSON.stringify(payload);
    if (!ref.current || ref.current.sig !== sig) ref.current = { sig, key: uuid() };
    return ref.current.key;
  }, []);
  const reset = useCallback(() => { ref.current = null; }, []);
  return { keyFor, reset };
}
