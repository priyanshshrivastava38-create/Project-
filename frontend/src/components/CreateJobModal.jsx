import { useEffect, useState } from 'react';
import { createJob } from '../api/production';
import { errorMessage, fieldErrors } from '../api/client';
import Modal from './Modal';
import Button from './Button';
import FormField from './FormField';
import { Alert } from './States';
import { useToast } from './Toast';
import { formatNumber, stripZeros, toNumber } from '../utils/format';
import { JOB_PRIORITIES } from '../utils/status';

/** line: an item_progress row from the order detail. */
export default function CreateJobModal({ open, line, onClose, onCreated }) {
  const toast = useToast();
  const remaining = line ? Math.max(0, (toNumber(line.quantity) || 0) - (toNumber(line.planned_quantity) || 0)) : 0;
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) {
      setForm({ planned_quantity: remaining ? stripZeros(String(remaining)) : '', target_date: '', priority: 'NORMAL', assigned_to: '', notes: '' });
      setErrors({}); setFormError('');
    }
  }, [open, remaining]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setPending(true); setErrors({}); setFormError('');
    try {
      const job = await createJob({
        order_item_id: line.id,
        planned_quantity: form.planned_quantity === '' ? null : form.planned_quantity,
        target_date: form.target_date || null,
        priority: form.priority,
        assigned_to: form.assigned_to.trim() || null,
        notes: form.notes.trim() || null,
      });
      toast.success(`Production job ${job.job_number} created`);
      onCreated?.(job);
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title={line ? `Create production job · line ${line.line_number}` : 'Create production job'} onClose={onClose} busy={pending}>
      {line ? (
        <form onSubmit={submit} className="stack" noValidate>
          <p className="muted-strong"><span className="mono">{line.sku}</span> {line.description}. Ordered {formatNumber(line.quantity)}, already planned {formatNumber(line.planned_quantity)}.</p>
          <div className="form-grid">
            <FormField label="Planned quantity" hint="Blank = remaining unplanned quantity" error={errors.planned_quantity}>
              <input type="number" min="0" step="any" value={form.planned_quantity} onChange={set('planned_quantity')} />
            </FormField>
            <FormField label="Target date" error={errors.target_date}>
              <input type="date" value={form.target_date} onChange={set('target_date')} />
            </FormField>
            <FormField label="Priority" error={errors.priority}>
              <select value={form.priority} onChange={set('priority')}>{JOB_PRIORITIES.map((p) => <option key={p}>{p}</option>)}</select>
            </FormField>
            <FormField label="Assigned to" error={errors.assigned_to}>
              <input value={form.assigned_to} onChange={set('assigned_to')} placeholder="e.g. Cell 2 – Day shift" />
            </FormField>
            <FormField label="Notes" className="full" error={errors.notes}>
              <textarea rows={2} value={form.notes} onChange={set('notes')} />
            </FormField>
          </div>
          {formError ? <Alert>{formError}</Alert> : null}
          <div className="modal-actions">
            <Button onClick={onClose} disabled={pending}>Cancel</Button>
            <Button type="submit" variant="primary" loading={pending}>Create job</Button>
          </div>
        </form>
      ) : null}
    </Modal>
  );
}
