import { useEffect, useState } from 'react';
import Modal from './Modal';
import Button from './Button';
import FormField from './FormField';
import { Alert } from './States';
import { errorMessage } from '../api/client';

/**
 * Confirmation dialog. With `reason` set it shows a required textarea
 * (min length `reasonMinLength`) and passes the text to onConfirm.
 * onConfirm should return a promise; the dialog stays open and shows the
 * error if it rejects or resolves to {ok:false, error}.
 */
export default function ConfirmDialog({
  open, title, message, confirmLabel = 'Confirm', tone = 'danger', onConfirm, onClose,
  reason = false, reasonLabel = 'Reason', reasonMinLength = 3, children,
}) {
  const [text, setText] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (open) { setText(''); setError(null); setPending(false); }
  }, [open]);

  const tooShort = reason && text.trim().length < reasonMinLength;

  const submit = async (e) => {
    e.preventDefault();
    if (tooShort) return;
    setPending(true);
    setError(null);
    try {
      const res = await onConfirm(reason ? text.trim() : undefined);
      if (res && res.ok === false) setError(res.error);
    } catch (err) {
      setError(err);
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title={title} onClose={onClose} busy={pending} size="sm">
      <form onSubmit={submit} className="stack">
        {message ? <p className="muted-strong">{message}</p> : null}
        {children}
        {reason ? (
          <FormField label={reasonLabel} required hint={`At least ${reasonMinLength} characters`}>
            <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} maxLength={500} />
          </FormField>
        ) : null}
        {error ? <Alert>{errorMessage(error)}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Back</Button>
          <Button type="submit" variant={tone === 'danger' ? 'danger' : 'primary'} loading={pending} disabled={tooShort}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
