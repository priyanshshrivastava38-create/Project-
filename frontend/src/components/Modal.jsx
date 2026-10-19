import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import Icon from './Icon';

export default function Modal({ open, title, onClose, children, footer, size = 'md', busy = false }) {
  const titleId = useId();
  const ref = useRef(null);
  const lastFocus = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    lastFocus.current = document.activeElement;
    const node = ref.current;
    const first = node?.querySelector('input:not([type=hidden]), select, textarea, button:not([data-close])');
    (first || node)?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape' && !busy) onCloseRef.current?.();
      if (e.key === 'Tab' && node) {
        const focusables = node.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
        if (!focusables.length) return;
        const f = focusables[0];
        const l = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === f) { e.preventDefault(); l.focus(); }
        else if (!e.shiftKey && document.activeElement === l) { e.preventDefault(); f.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      if (lastFocus.current && lastFocus.current.focus) lastFocus.current.focus();
    };
  }, [open, busy]);

  if (!open) return null;
  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose?.(); }}>
      <div className={`modal modal-${size}`} role="dialog" aria-modal="true" aria-labelledby={titleId} ref={ref} tabIndex={-1}>
        <div className="modal-header">
          <h2 id={titleId} className="modal-title">{title}</h2>
          <button type="button" className="icon-btn" data-close onClick={onClose} aria-label="Close dialog" disabled={busy}>
            <Icon name="close" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
