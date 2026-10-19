import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  advanceJob, allocateMaterials, cancelJob, completeJob, getJob, recordOutput, startJob,
} from '../api/production';
import { listInspections } from '../api/quality';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useAction } from '../hooks/useAction';
import { useAuth } from '../context/AuthContext';
import {
  Alert, Button, Card, ConfirmDialog, ErrorState, FormField, KeyValue, Modal, PageHeader, ProgressBar, Spinner,
  StatusBadge, useToast,
} from '../components';
import InspectionFormModal from '../components/InspectionFormModal';
import { formatDate, formatDateTime, formatNumber, formatQty, toNumber } from '../utils/format';

const QUALITY_STAGE = 'QUALITY_INSPECTION';
const OPEN = ['PLANNED', 'IN_PROGRESS'];

function RecordOutputModal({ open, job, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) { setForm({ good_quantity: '', scrap_quantity: '0', notes: '' }); setErrors({}); setFormError(''); }
  }, [open]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  // Mirrors the backend cap: good output may not exceed planned − (produced − QC rejected).
  const maxGood = job ? (toNumber(job.planned_quantity) || 0) - ((toNumber(job.produced_quantity) || 0) - (toNumber(job.qc_rejected_quantity) || 0)) : 0;

  const submit = async (e) => {
    e.preventDefault();
    const good = toNumber(form.good_quantity || 0);
    const scrap = toNumber(form.scrap_quantity || 0);
    const errs = {};
    if (good === null || good < 0) errs.good_quantity = 'Invalid quantity';
    else if (good > maxGood) errs.good_quantity = `At most ${formatNumber(maxGood)} more good units`;
    if (scrap === null || scrap < 0) errs.scrap_quantity = 'Invalid quantity';
    if (!errs.good_quantity && !errs.scrap_quantity && good + scrap <= 0) errs.good_quantity = 'Report at least one good or scrapped unit';
    setErrors(errs); setFormError('');
    if (Object.keys(errs).length) return;
    setPending(true);
    try {
      const out = await recordOutput(job.id, {
        good_quantity: form.good_quantity || 0, scrap_quantity: form.scrap_quantity || 0, notes: form.notes.trim() || null,
      });
      toast.success(`Batch ${out.batch_ref} recorded`);
      onSaved?.(out);
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title="Record production output" onClose={onClose} busy={pending}>
      {job ? (
        <form onSubmit={submit} className="stack" noValidate>
          <p className="muted-strong">Recording output consumes allocated material for good and scrapped units. Up to {formatQty(maxGood, job.product.uom)} more good units can be reported.</p>
          <div className="form-grid">
            <FormField label="Good quantity" required error={errors.good_quantity}>
              <input type="number" min="0" step="any" value={form.good_quantity ?? ''} onChange={set('good_quantity')} />
            </FormField>
            <FormField label="Scrap quantity" error={errors.scrap_quantity}>
              <input type="number" min="0" step="any" value={form.scrap_quantity ?? ''} onChange={set('scrap_quantity')} />
            </FormField>
            <FormField label="Notes" className="full" error={errors.notes}>
              <textarea rows={2} maxLength={500} value={form.notes ?? ''} onChange={set('notes')} />
            </FormField>
          </div>
          {formError ? <Alert>{formError}</Alert> : null}
          <div className="modal-actions">
            <Button onClick={onClose} disabled={pending}>Cancel</Button>
            <Button type="submit" variant="primary" loading={pending}>Record output</Button>
          </div>
        </form>
      ) : null}
    </Modal>
  );
}

function AdvanceModal({ open, current, next, onClose, onConfirm }) {
  const [notes, setNotes] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => { if (open) { setNotes(''); setError(null); } }, [open]);

  const submit = async (e) => {
    e.preventDefault();
    setPending(true); setError(null);
    const res = await onConfirm(notes.trim());
    setPending(false);
    if (res && res.ok === false) setError(res.error);
  };

  return (
    <Modal open={open} title="Advance stage" onClose={onClose} busy={pending} size="sm">
      <form onSubmit={submit} className="stack">
        <p className="muted-strong">Complete <strong>{current?.stage_name}</strong> and move the job to <strong>{next?.stage_name}</strong>. Stages cannot be skipped or reversed.</p>
        <FormField label="Stage notes" hint="Optional, saved on the completed stage">
          <textarea rows={2} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </FormField>
        {error ? <Alert>{errorMessage(error)}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Back</Button>
          <Button type="submit" variant="primary" loading={pending}>Advance</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function JobDetailPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const action = useAction();
  const { data: j, error, reload } = useAsync(() => getJob(id), [id]);
  const canQualityRead = can('quality:read');
  const insp = useAsync(() => listInspections({ job_id: id, page_size: 100 }), [id], { enabled: canQualityRead });
  const [dialog, setDialog] = useState(null); // 'output' | 'advance' | 'complete' | 'cancel' | 'inspect'
  const [reinspecting, setReinspecting] = useState(null);

  if (error && !j) return <ErrorState error={error} onRetry={reload} />;
  if (!j) return <Spinner />;

  const refresh = () => { reload(); if (canQualityRead) insp.reload(); };
  const close = () => setDialog(null);
  const s = j.status;
  const uom = j.product.uom;
  const canWrite = can('production:write');
  const current = j.current_stage;
  const nextStage = current ? j.stages.find((st) => st.sequence > current.sequence) : null;
  const atQc = s === 'IN_PROGRESS' && current?.stage_code === QUALITY_STAGE;
  const atLast = s === 'IN_PROGRESS' && current && !nextStage;
  const hasOutput = (toNumber(j.produced_quantity) || 0) > 0 || (toNumber(j.scrap_quantity) || 0) > 0;
  const shortfall = j.materials.some((m) => (toNumber(m.shortfall) || 0) > 0);
  const needsOutputForQc = nextStage?.stage_code === QUALITY_STAGE && !((toNumber(j.produced_quantity) || 0) > 0);
  const canInspect = can('quality:write') && atQc;
  const run = (key, fn, success) => action.run(key, fn, { success, onSuccess: refresh });

  const qtys = [
    ['Planned', j.planned_quantity], ['Produced (good)', j.produced_quantity], ['Pending inspection', j.pending_inspection_quantity],
    ['Approved', j.approved_quantity], ['On hold', j.hold_quantity], ['QC rejected', j.qc_rejected_quantity], ['Scrap', j.scrap_quantity],
  ];

  return (
    <>
      <PageHeader
        title={j.job_number}
        meta={(
          <>
            <StatusBadge status={s} />
            <StatusBadge status={j.priority} />
            {j.is_overdue ? <StatusBadge status="OVERDUE" label="Overdue" tone="red" /> : null}
          </>
        )}
        subtitle={(
          <>
            <span className="mono">{j.product.sku}</span> {j.product.name}{' · '}
            {can('orders:read') ? <Link to={`/orders/${j.order.id}`}>{j.order.order_number}</Link> : j.order.order_number}
          </>
        )}
        breadcrumbs={[{ label: 'Production', to: '/production' }, { label: 'Jobs', to: '/production/jobs' }, { label: j.job_number }]}
        actions={(
          <>
            {can('inventory:reserve') && OPEN.includes(s) && shortfall ? (
              <Button icon="inventory" loading={action.isPending('allocate')} disabled={action.anyPending}
                onClick={() => run('allocate', () => allocateMaterials(j.id), 'Materials allocated')}>
                Allocate materials
              </Button>
            ) : null}
            {canWrite && s === 'PLANNED' ? (
              <Button variant="primary" icon="check" loading={action.isPending('start')} disabled={action.anyPending || !j.materials_ready}
                title={j.materials_ready ? undefined : 'Allocate all required materials first'}
                onClick={() => run('start', () => startJob(j.id), `${j.job_number} started`)}>
                Start job
              </Button>
            ) : null}
            {canWrite && s === 'IN_PROGRESS' ? <Button icon="plus" disabled={action.anyPending} onClick={() => setDialog('output')}>Record output</Button> : null}
            {canWrite && s === 'IN_PROGRESS' && nextStage ? (
              <Button icon="chevronRight" disabled={action.anyPending || needsOutputForQc}
                title={needsOutputForQc ? 'Record production output before moving to quality inspection' : undefined}
                onClick={() => setDialog('advance')}>
                Advance to {nextStage.stage_name}
              </Button>
            ) : null}
            {canInspect ? <Button icon="quality" disabled={action.anyPending} onClick={() => setDialog('inspect')}>Record inspection</Button> : null}
            {canWrite && atLast ? <Button variant="primary" icon="check" disabled={action.anyPending} onClick={() => setDialog('complete')}>Complete job</Button> : null}
            {canWrite && OPEN.includes(s) && !hasOutput ? <Button variant="danger-outline" onClick={() => setDialog('cancel')}>Cancel job</Button> : null}
          </>
        )}
      />

      {s === 'PLANNED' && !j.materials_ready ? (
        <Alert tone="warning" title="Materials not fully allocated">The job can start once every required material is reserved.</Alert>
      ) : null}

      <div className="grid-2 section-gap">
        <Card title="Summary">
          <KeyValue items={[
            ['Order', can('orders:read') ? <Link key="o" to={`/orders/${j.order.id}`}>{j.order.order_number}</Link> : j.order.order_number],
            ['Order required by', formatDate(j.order.required_date)],
            ['Assigned to', j.assigned_to],
            ['Start date', formatDate(j.start_date)],
            ['Target date', <span key="t" className={j.is_overdue ? 'tone-text-red' : ''}>{formatDate(j.target_date)}</span>],
            ['Started', j.started_at ? formatDateTime(j.started_at) : null],
            ['Completed', j.actual_completion_at ? formatDateTime(j.actual_completion_at) : null],
            ['Created', formatDateTime(j.created_at)],
            ['Notes', j.notes],
          ]} />
        </Card>
        <Card title="Quantities" subtitle={`In ${uom}`}>
          <div className="qty-grid">
            {qtys.map(([label, v]) => (
              <div key={label} className="qty-box"><div className="lbl">{label}</div><div className="val">{formatNumber(v)}</div></div>
            ))}
          </div>
          <div className="section-gap">
            <ProgressBar value={toNumber(j.approved_quantity)} max={toNumber(j.planned_quantity)} tone="green" label="Approved of planned" />
            <div className="progress-legend">
              <span>Approved {Math.round(((toNumber(j.approved_quantity) || 0) / (toNumber(j.planned_quantity) || 1)) * 100)}% of planned</span>
            </div>
          </div>
        </Card>
      </div>

      <Card title="Stages" subtitle={current && s === 'IN_PROGRESS' ? `Current: ${current.stage_name}` : undefined}>
        <ol className="stepper" aria-label="Production stages">
          {j.stages.map((st) => (
            <li key={st.sequence} className={`step ${st.status === 'DONE' ? 'done' : st.status === 'IN_PROGRESS' ? 'current' : ''}`}
              aria-current={st.status === 'IN_PROGRESS' ? 'step' : undefined}>
              <span className="step-dot">{st.status === 'DONE' ? '✓' : st.sequence}</span>
              <span>{st.stage_name}</span>
              <span className="muted small">{st.completed_at ? formatDateTime(st.completed_at) : st.started_at ? `Started ${formatDateTime(st.started_at)}` : ''}</span>
            </li>
          ))}
        </ol>
        {j.stages.some((st) => st.notes) ? (
          <ul className="history-list section-gap">
            {j.stages.filter((st) => st.notes).map((st) => <li key={st.sequence}><strong>{st.stage_name}:</strong> {st.notes}</li>)}
          </ul>
        ) : null}
      </Card>

      <Card title="Material allocations" subtitle={j.materials_ready ? 'All outstanding requirements are allocated.' : 'Some requirements are not yet allocated.'} padded={false}>
        {j.materials.length ? (
          <div className="table-scroll">
            <table className="table table-dense">
              <thead><tr><th>Material</th><th className="num">Required</th><th className="num">Allocated</th><th className="num">Consumed</th><th className="num">Shortfall</th><th className="num">In stock (available)</th></tr></thead>
              <tbody>
                {j.materials.map((m) => (
                  <tr key={m.material_id} className={(toNumber(m.shortfall) || 0) > 0 ? 'row-warn' : ''}>
                    <td><span className="mono">{m.sku}</span><div className="small muted">{m.name}</div></td>
                    <td className="num">{formatQty(m.required, m.uom)}</td>
                    <td className="num">{formatQty(m.allocated, m.uom)}</td>
                    <td className="num">{formatQty(m.consumed, m.uom)}</td>
                    <td className={`num ${(toNumber(m.shortfall) || 0) > 0 ? 'tone-text-red' : ''}`}>{formatQty(m.shortfall, m.uom)}</td>
                    <td className="num">{formatQty(m.available_in_stock, m.uom)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="muted card-body">This product has no bill of materials.</p>}
        {j.reservations.length ? (
          <div className="table-scroll">
            <table className="table table-dense">
              <thead><tr><th>Reservation</th><th>Warehouse</th><th className="num">Reserved</th><th className="num">Consumed</th><th className="num">Remaining</th><th>Status</th><th>Created</th></tr></thead>
              <tbody>
                {j.reservations.map((r) => {
                  const item = r.balance.material || r.balance.product;
                  return (
                    <tr key={r.id}>
                      <td><span className="mono">{item?.sku}</span></td>
                      <td>{r.balance.warehouse.code}</td>
                      <td className="num">{formatQty(r.quantity, item?.uom)}</td>
                      <td className="num">{formatQty(r.consumed_quantity, item?.uom)}</td>
                      <td className="num">{formatQty(r.remaining, item?.uom)}</td>
                      <td><StatusBadge status={r.status} /></td>
                      <td>{formatDateTime(r.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>

      <div className="grid-2 section-gap">
        <Card title="Production output" padded={false}>
          {j.outputs.length ? (
            <table className="table table-dense">
              <thead><tr><th>Batch</th><th className="num">Good</th><th className="num">Scrap</th><th>Recorded</th></tr></thead>
              <tbody>
                {j.outputs.map((o) => (
                  <tr key={o.id}>
                    <td><span className="mono">{o.batch_ref}</span>{o.notes ? <div className="small muted">{o.notes}</div> : null}</td>
                    <td className="num">{formatNumber(o.good_quantity)}</td>
                    <td className="num">{formatNumber(o.scrap_quantity)}</td>
                    <td>{formatDateTime(o.recorded_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted card-body">No output recorded yet.</p>}
        </Card>
        {canQualityRead ? (
          <Card title="Quality inspections" padded={false}
            actions={<Link to={`/quality?job=${j.id}`} className="small">Open in Quality</Link>}>
            {insp.error ? <ErrorState error={insp.error} onRetry={insp.reload} /> : !insp.data ? <Spinner /> : insp.data.items.length ? (
              <table className="table table-dense">
                <thead><tr><th>Inspection</th><th>Outcome</th><th className="num">Inspected</th><th className="num">Approved</th><th className="num">Defects</th><th /></tr></thead>
                <tbody>
                  {insp.data.items.map((i) => (
                    <tr key={i.id}>
                      <td>
                        <strong>{i.inspection_number}</strong>{i.batch_ref ? <span className="mono small"> · {i.batch_ref}</span> : null}
                        <div className="small muted">{formatDateTime(i.inspected_at)}{i.inspector ? ` · ${i.inspector.full_name}` : ''}{i.parent_id ? ' · re-inspection' : ''}</div>
                      </td>
                      <td><StatusBadge status={i.outcome} />{i.reinspected ? <div className="small muted">Reinspected</div> : null}</td>
                      <td className="num">{formatNumber(i.quantity_inspected)}</td>
                      <td className="num">{formatNumber(i.approved_quantity)}</td>
                      <td className="num">{formatNumber(i.defect_quantity)}</td>
                      <td>
                        {canInspect && i.outcome === 'FAIL' && !i.reinspected ? (
                          <Button size="sm" onClick={() => setReinspecting(i)}>Re-inspect</Button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="muted card-body">No inspections yet.</p>}
          </Card>
        ) : null}
      </div>

      <RecordOutputModal open={dialog === 'output'} job={j} onClose={close} onSaved={() => { close(); refresh(); }} />
      <AdvanceModal
        open={dialog === 'advance'}
        current={current}
        next={nextStage}
        onClose={close}
        onConfirm={(notes) => action.run('advance', () => advanceJob(j.id, notes), {
          success: `Moved to ${nextStage?.stage_name}`, toastError: false, onSuccess: () => { close(); refresh(); },
        })}
      />
      <ConfirmDialog
        open={dialog === 'complete'}
        title={`Complete ${j.job_number}`}
        message="All planned units must have passed inspection. Unused material reservations will be released."
        confirmLabel="Complete job"
        tone="primary"
        onClose={close}
        onConfirm={() => action.run('complete', () => completeJob(j.id), {
          success: `${j.job_number} completed`, toastError: false, onSuccess: () => { close(); refresh(); },
        })}
      />
      <ConfirmDialog
        open={dialog === 'cancel'}
        title={`Cancel ${j.job_number}`}
        message="Reserved material will be released. This cannot be undone."
        confirmLabel="Cancel job"
        reason
        reasonLabel="Cancellation reason"
        onClose={close}
        onConfirm={(reason) => action.run('cancel', () => cancelJob(j.id, reason), {
          success: `${j.job_number} cancelled`, toastError: false, onSuccess: () => { close(); refresh(); },
        })}
      />
      <InspectionFormModal open={dialog === 'inspect'} jobId={j.id} onClose={close} onSaved={() => { close(); refresh(); }} />
      <InspectionFormModal open={!!reinspecting} mode="reinspect" parent={reinspecting} onClose={() => setReinspecting(null)}
        onSaved={() => { setReinspecting(null); refresh(); }} />
    </>
  );
}
