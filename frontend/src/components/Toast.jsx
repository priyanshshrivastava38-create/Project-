import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import Icon from './Icon';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const push = useCallback((type, message, { timeout } = {}) => {
    const id = nextId.current++;
    setToasts((t) => [...t.slice(-4), { id, type, message }]);
    const ms = timeout ?? (type === 'error' ? 7000 : 4000);
    if (ms > 0) setTimeout(() => dismiss(id), ms);
    return id;
  }, [dismiss]);

  const api = useMemo(() => ({
    success: (m, o) => push('success', m, o),
    error: (m, o) => push('error', m, o),
    info: (m, o) => push('info', m, o),
    dismiss,
  }), [push, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-region" aria-live="polite" aria-relevant="additions">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`} role={t.type === 'error' ? 'alert' : 'status'}>
            <Icon name={t.type === 'success' ? 'check' : t.type === 'error' ? 'alert' : 'info'} />
            <span className="toast-msg">{t.message}</span>
            <button type="button" className="icon-btn" onClick={() => dismiss(t.id)} aria-label="Dismiss notification">
              <Icon name="close" size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
