import { useEffect, useState } from 'react';
import { createInspection, reinspect } from '../api/quality';
import { getJob, listJobs } from '../api/production';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import Modal from './Modal';
import Button from './Button';
import FormField from './FormField';
import Icon from './Icon';
import { Alert } from './States';
import { useToast } from './Toast';
import { formatNumber, stripZeros, toNumber } from '../utils/format';

const DEFAULT_CHECKS = ['Dimensions within tolerance', 'Surface finish', 'Visual / weld quality'];
const blankChecklist = () => DEFAULT_CHECKS.map((check) => ({ check, passed: true, note: '' }));

/**
 * mode "create": record a new inspection (optionally for a fixed jobId).
 * mode "reinspect": re-inspect a FAILED inspection (`parent`).
 */
export default function InspectionFormModal({ open, mode = 'create', jobId, parent, onClose, onSaved }) {
  const toast = useToast();
  const isRe = mode === 'reinspect';
  const jobs = useAsync(() => listJobs({ stage: 'QUALITY_INSPECTION', page_size: 200 }), [open], { enabled: open && !isRe && !jobId });
  const [form, setForm] = useState({});
  const [checklist, setChecklist] = useState(blankChecklist);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);
  const selectedJobId = jobId ? String(jobId) : form.production_job_id;
  const job = useAsync(() => getJob(selectedJobId), [selectedJobId, open], { enabled: open && !isRe && Boolean(selectedJobId) });

  useEffect(() => {
    if (!open) return;
    setForm({
      production_job_id: jobId ? String(jobId) : '',
      batch_ref: '',
      quantity_inspected: '',
      defect_quantity: '0',
      outcome: 'PASS',
      defect_description: '',
      corrective_action: '',
      comments: '',
    });
    setChecklist(isRe && parent?.checklist?.length ? parent.checklist.map((c) => ({ check: c.check, passed: c.passed, note: c.note || '' })) : blankChecklist());
    setErrors({}); setFormError('');
  }, [open, jobId, isRe, parent]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const setCheck = (i, patch) => setChecklist((cl) => cl.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  const j = job.data;
  const defects = toNumber(form.defect_quantity) || 0;
  const needsDescription = form.outcome === 'FAIL' || defects > 0;

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!isRe && !selectedJobId) errs.production_job_id = 'Select a job';
    if (!isRe && !(toNumber(form.quantity_inspected) > 0)) errs.quantity_inspected = 'Must be greater than 0';
    if (defects < 0 || toNumber(form.defect_quantity) === null) errs.defect_quantity = 'Invalid number';
    else if (!isRe && defects > (toNumber(form.quantity_inspected) || 0)) errs.defect_quantity = 'Cannot exceed quantity inspected';
    if (needsDescription && !form.defect_description.trim()) errs.defect_description = 'Required when the outcome is FAIL or defects are recorded';
    if (isRe && form.corrective_action.trim().length < 3) errs.corrective_action = 'Corrective action is required (min 3 characters)';
    checklist.forEach((c, i) => { if (!c.check.trim()) errs[`checklist.${i}`] = 'Describe the check or remove the row'; });
    setErrors(errs); setFormError('');
    if (Object.keys(errs).length) return;

    const cl = checklist.map((c) => ({ check: c.check.trim(), passed: c.passed, note: c.note.trim() || null }));
    setPending(true);
    try {
      let saved;
      if (isRe) {
        saved = await reinspect(parent.id, {
          defect_quantity: form.defect_quantity || 0,
          outcome: form.outcome,
          checklist: cl,
          defect_description: form.defect_description.trim() || null,
          corrective_action: form.corrective_action.trim(),
          comments: form.comments.trim() || null,
        });
      } else {
        saved = await createInspection({
          production_job_id: Number(selectedJobId),
          batch_ref: form.batch_ref || null,
          quantity_inspected: form.quantity_inspected,
          defect_quantity: form.defect_quantity || 0,
          outcome: form.outcome,
          checklist: cl,
          defect_description: form.defect_description.trim() || null,
          corrective_action: form.corrective_action.trim() || null,
          comments: form.comments.trim() || null,
        });
      }
      toast.success(`Inspection ${saved.inspection_number} recorded (${saved.outcome})`);
      onSaved?.(saved);
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  const title = isRe ? `Re-inspect ${parent?.inspection_number || ''}` : 'Record inspection';

  return (
    <Modal open={open} title={title} onClose={onClose} busy={pending} size="lg">
      <form onSubmit={submit} className="stack" noValidate>
        {isRe && parent ? (
          <Alert tone="info">
            Re-inspecting units held from {parent.inspection_number} (job {parent.job.job_number}): {formatNumber(parent.defect_quantity)} defective of {formatNumber(parent.quantity_inspected)} inspected.
          </Alert>
        ) : null}
        <div className="form-grid">
          {!isRe ? (
            <>
              <FormField label="Production job" required error={errors.production_job_id} hint={jobId ? undefined : 'Only in-progress jobs at the Quality inspection stage'}>
                <select value={selectedJobId || ''} onChange={set('production_job_id')} disabled={Boolean(jobId)}>
                  {jobId ? <option value={jobId}>{j ? `${j.job_number} · ${j.product.sku}` : `Job #${jobId}`}</option> : (
                    <>
                      <option value="">{jobs.loading ? 'Loading…' : (jobs.data?.items?.length ? 'Select job' : 'No jobs awaiting inspection')}</option>
                      {(jobs.data?.items || []).map((x) => <option key={x.id} value={x.id}>{x.job_number} · {x.order.order_number} · {x.product.sku} (pending {formatNumber(x.pending_inspection_quantity)})</option>)}
                    </>
                  )}
                </select>
              </FormField>
              <FormField label="Batch (optional)" error={errors.batch_ref}>
                <select value={form.batch_ref || ''} onChange={set('batch_ref')} disabled={!j}>
                  <option value="">Any / not batch-specific</option>
                  {(j?.outputs || []).map((o) => <option key={o.id} value={o.batch_ref}>{o.batch_ref} · {formatNumber(o.good_quantity)} good</option>)}
                </select>
              </FormField>
              {j ? (
                <p className="muted small full">
                  {j.job_number}: produced {formatNumber(j.produced_quantity)}, pending inspection <strong>{formatNumber(j.pending_inspection_quantity)}</strong>, approved {formatNumber(j.approved_quantity)}.
                  {j.current_stage?.stage_code !== 'QUALITY_INSPECTION' ? ' This job is not at the Quality inspection stage yet, so the server may refuse the inspection.' : ''}
                </p>
              ) : null}
              <FormField label="Quantity inspected" required error={errors.quantity_inspected}>
                <input type="number" min="0" step="any" value={form.quantity_inspected || ''} onChange={set('quantity_inspected')}
                  placeholder={j ? stripZeros(j.pending_inspection_quantity) : ''} />
              </FormField>
            </>
          ) : null}
          <FormField label="Defect quantity" error={errors.defect_quantity}>
            <input type="number" min="0" step="any" value={form.defect_quantity ?? ''} onChange={set('defect_quantity')} />
          </FormField>
          <fieldset className="full" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="field-label">Outcome <span className="req">*</span></legend>
            <div className="row" style={{ marginTop: 6 }}>
              {['PASS', 'FAIL'].map((o) => (
                <label key={o} className="checkbox">
                  <input type="radio" name="outcome" value={o} checked={form.outcome === o} onChange={set('outcome')} /> {o === 'PASS' ? 'Pass' : 'Fail'}
                </label>
              ))}
            </div>
          </fieldset>
        </div>

        <div>
          <div className="row-between" style={{ marginBottom: 8 }}>
            <span className="field-label">Checklist</span>
            <Button size="sm" icon="plus" onClick={() => setChecklist((cl) => [...cl, { check: '', passed: true, note: '' }])}>Add check</Button>
          </div>
          <div className="stack-sm">
            {checklist.map((c, i) => (
              <div key={i}>
                <div className="checklist-row">
                  <input className="inline-control" aria-label={`Check ${i + 1}`} value={c.check} onChange={(e) => setCheck(i, { check: e.target.value })} maxLength={200} placeholder="Check" />
                  <label className="checkbox"><input type="checkbox" checked={c.passed} onChange={(e) => setCheck(i, { passed: e.target.checked })} /> Passed</label>
                  <input className="inline-control" aria-label={`Note for check ${i + 1}`} value={c.note} onChange={(e) => setCheck(i, { note: e.target.value })} placeholder="Note (optional)" />
                  <button type="button" className="icon-btn" aria-label={`Remove check ${i + 1}`} onClick={() => setChecklist((cl) => cl.filter((_, k) => k !== i))}><Icon name="close" size={14} /></button>
                </div>
                {errors[`checklist.${i}`] ? <div className="field-err">{errors[`checklist.${i}`]}</div> : null}
              </div>
            ))}
            {!checklist.length ? <span className="muted small">No checklist items.</span> : null}
          </div>
        </div>

        <div className="form-grid">
          <FormField label="Defect description" required={needsDescription} error={errors.defect_description} className="full">
            <textarea rows={2} value={form.defect_description || ''} onChange={set('defect_description')} />
          </FormField>
          <FormField label="Corrective action" required={isRe} error={errors.corrective_action}>
            <textarea rows={2} value={form.corrective_action || ''} onChange={set('corrective_action')} />
          </FormField>
          <FormField label="Comments" error={errors.comments}>
            <textarea rows={2} value={form.comments || ''} onChange={set('comments')} />
          </FormField>
        </div>
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>{isRe ? 'Record re-inspection' : 'Record inspection'}</Button>
        </div>
      </form>
    </Modal>
  );
}
