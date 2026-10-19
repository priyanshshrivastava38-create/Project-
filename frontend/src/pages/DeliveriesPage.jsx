import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  cancelDelivery, confirmDelivery, dispatchDelivery, failDelivery, listDeliveries, markInTransit, markReady,
} from '../api/deliveries';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useAction } from '../hooks/useAction';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { useAuth } from '../context/AuthContext';
import {
  Alert, Button, ConfirmDialog, DataTable, FilterSelect, FiltersBar, FormField, KeyValue, Modal, PageHeader,
  SearchInput, StatusBadge, useToast,
} from '../components';
import CreateDeliveryModal from '../components/CreateDeliveryModal';
import { formatDate, formatDateTime, formatNumber, humanize } from '../utils/format';
import { DELIVERY_STATUSES } from '../utils/status';

const FORMS = {
  dispatch: {
    title: 'Dispatch', submit: 'Dispatch', api: dispatchDelivery,
    fields: [
      { key: 'carrier', label: 'Carrier', required: true, min: 2, max: 120 },
      { key: 'tracking_number', label: 'Tracking number', required: true, min: 2, max: 120 },
    ],
    init: (d) => ({ carrier: d.carrier || '', tracking_number: d.tracking_number || '' }),
  },
  confirm: {
    title: 'Confirm delivery of', submit: 'Confirm delivered', api: confirmDelivery,
    fields: [
      { key: 'received_by', label: 'Received by', required: true, min: 2, max: 120 },
      { key: 'delivered_at', label: 'Delivered at', type: 'datetime-local', hint: 'Blank = now' },
      { key: 'proof_of_delivery_ref', label: 'Proof of delivery ref', max: 200 },
      { key: 'notes', label: 'Notes', textarea: true, max: 1000 },
    ],
    init: () => ({ received_by: '', delivered_at: '', proof_of_delivery_ref: '', notes: '' }),
  },
};

/** Small form for the dispatch / confirm-delivery transitions. */
function TransitionModal({ kind, delivery, onClose, onSaved }) {
  const toast = useToast();
  const cfg = FORMS[kind];
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (cfg && delivery) { setForm(cfg.init(delivery)); setErrors({}); setFormError(''); }
  }, [cfg, delivery]);

  if (!cfg || !delivery) return null;

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    cfg.fields.forEach((fd) => {
      const v = (form[fd.key] || '').trim();
      if (fd.required && v.length < (fd.min || 1)) errs[fd.key] = `At least ${fd.min || 1} characters`;
    });
    setErrors(errs); setFormError('');
    if (Object.keys(errs).length) return;
    const body = Object.fromEntries(cfg.fields.map((fd) => {
      const v = (form[fd.key] || '').trim();
      if (fd.type === 'datetime-local') return [fd.key, v ? new Date(v).toISOString() : null];
      return [fd.key, v || null];
    }));
    setPending(true);
    try {
      const d = await cfg.api(delivery.id, body);
      toast.success(`${d.delivery_number} ${humanize(d.status).toLowerCase()}`);
      onSaved?.(d);
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open title={`${cfg.title} ${delivery.delivery_number}`} onClose={onClose} busy={pending}>
      <form onSubmit={submit} className="stack" noValidate>
        <div className="form-grid">
          {cfg.fields.map((fd) => (
            <FormField key={fd.key} label={fd.label} required={fd.required} hint={fd.hint} error={errors[fd.key]} className={fd.textarea ? 'full' : ''}>
              {fd.textarea ? (
                <textarea rows={2} maxLength={fd.max} value={form[fd.key] ?? ''} onChange={(e) => setForm((f) => ({ ...f, [fd.key]: e.target.value }))} />
              ) : (
                <input type={fd.type || 'text'} maxLength={fd.max} value={form[fd.key] ?? ''} onChange={(e) => setForm((f) => ({ ...f, [fd.key]: e.target.value }))} />
              )}
            </FormField>
          ))}
        </div>
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>{cfg.submit}</Button>
        </div>
      </form>
    </Modal>
  );
}

function DeliveryDetails({ d }) {
  return (
    <div className="grid-2">
      <table className="table table-dense">
        <thead><tr><th>Line</th><th className="num">Quantity</th></tr></thead>
        <tbody>
          {d.items.map((it) => (
            <tr key={it.id}><td><span className="mono">{it.sku}</span><div className="small muted">{it.description}</div></td><td className="num">{formatNumber(it.quantity)}</td></tr>
          ))}
        </tbody>
      </table>
      <KeyValue items={[
        ['Planned dispatch', formatDate(d.planned_dispatch_date)],
        ['Dispatched', d.dispatched_at ? formatDateTime(d.dispatched_at) : null],
        ['Carrier', d.carrier],
        ['Tracking number', d.tracking_number],
        ['Delivered', d.delivered_at ? formatDateTime(d.delivered_at) : null],
        ['Received by', d.received_by],
        ['Proof of delivery', d.proof_of_delivery_ref],
        d.failure_reason ? [d.status === 'CANCELLED' ? 'Cancellation reason' : 'Failure reason', d.failure_reason] : null,
        ['Notes', d.notes],
      ]} />
    </div>
  );
}

export default function DeliveriesPage() {
  const { can } = useAuth();
  const action = useAction();
  const [params] = useSearchParams();
  const highlight = params.get('highlight');
  const pg = usePagination({ status: params.get('status') || '' });
  const [search, setSearch] = useState(params.get('q') || '');
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const f = pg.filters;
  const { data, error, loading, reload } = useAsync(
    () => listDeliveries({ ...pg.params, q }),
    [pg.page, pg.pageSize, f.status, q],
  );
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(null); // { kind: 'dispatch' | 'confirm', d }
  const [dialog, setDialog] = useState(null); // { kind: 'cancel' | 'fail', d }
  const [returnToStock, setReturnToStock] = useState(true);
  const canWrite = can('deliveries:write');

  const step = (key, d, fn, verb) => action.run(`${key}-${d.id}`, fn, { success: `${d.delivery_number} ${verb}`, onSuccess: reload });
  const closeDialog = () => setDialog(null);

  const rowActions = (d) => {
    const s = d.status;
    const busy = action.anyPending;
    return (
      <div className="row">
        {s === 'PENDING' ? (
          <Button size="sm" loading={action.isPending(`ready-${d.id}`)} disabled={busy}
            title="Reserves the finished goods for this delivery"
            onClick={() => step('ready', d, () => markReady(d.id), 'is ready for dispatch')}>Mark ready</Button>
        ) : null}
        {s === 'READY_FOR_DISPATCH' ? <Button size="sm" variant="primary" icon="deliveries" disabled={busy} onClick={() => setForm({ kind: 'dispatch', d })}>Dispatch</Button> : null}
        {s === 'DISPATCHED' ? (
          <Button size="sm" loading={action.isPending(`transit-${d.id}`)} disabled={busy}
            onClick={() => step('transit', d, () => markInTransit(d.id), 'is in transit')}>In transit</Button>
        ) : null}
        {['DISPATCHED', 'IN_TRANSIT'].includes(s) ? (
          <>
            <Button size="sm" variant="primary" icon="check" disabled={busy} onClick={() => setForm({ kind: 'confirm', d })}>Delivered</Button>
            <Button size="sm" variant="danger-outline" disabled={busy} onClick={() => { setReturnToStock(true); setDialog({ kind: 'fail', d }); }}>Failed</Button>
          </>
        ) : null}
        {['PENDING', 'READY_FOR_DISPATCH'].includes(s) ? (
          <Button size="sm" variant="danger-outline" disabled={busy} onClick={() => setDialog({ kind: 'cancel', d })}>Cancel</Button>
        ) : null}
      </div>
    );
  };

  const columns = [
    { key: 'delivery_number', header: 'Delivery', render: (r) => <strong>{r.delivery_number}</strong> },
    { key: 'order', header: 'Order', render: (r) => (can('orders:read') ? <Link to={`/orders/${r.order.id}`}>{r.order.order_number}</Link> : r.order.order_number) },
    { key: 'customer_name', header: 'Customer' },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'items', header: 'Lines', render: (r) => (
      <span className="chip-list">{r.items.map((it) => <span key={it.id} className="chip">{it.sku} × {formatNumber(it.quantity)}</span>)}</span>
    ) },
    { key: 'planned_dispatch_date', header: 'Planned', render: (r) => formatDate(r.planned_dispatch_date) },
    { key: 'carrier', header: 'Carrier / tracking', render: (r) => (r.carrier ? <div>{r.carrier}{r.tracking_number ? <div className="mono small">{r.tracking_number}</div> : null}</div> : '—') },
    ...(canWrite ? [{ key: 'actions', header: '', render: rowActions }] : []),
  ];

  const d = dialog?.d;

  return (
    <>
      <PageHeader
        title="Deliveries"
        subtitle="Shipments of QC-approved goods: ready → dispatched → in transit → delivered."
        actions={canWrite ? <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>Create delivery</Button> : null}
      />
      <FiltersBar onReset={() => { setSearch(''); pg.setFilters({ status: '' }); }}>
        <SearchInput value={search} onChange={setSearch} placeholder="Delivery, order or tracking number…" />
        <FilterSelect label="Status" value={f.status} onChange={(v) => pg.setFilter('status', v)} options={DELIVERY_STATUSES.map((s) => ({ value: s, label: humanize(s) }))} />
      </FiltersBar>
      <DataTable
        columns={columns}
        rows={data?.items}
        loading={loading}
        error={error}
        onRetry={reload}
        page={pg.page}
        pageSize={pg.pageSize}
        total={data?.total}
        onPageChange={pg.setPage}
        onPageSizeChange={pg.setPageSize}
        renderExpanded={(r) => <DeliveryDetails d={r} />}
        rowClassName={(r) => (highlight && String(r.id) === highlight ? 'row-warn' : '')}
        emptyTitle="No deliveries match"
        emptyMessage={canWrite ? 'Create a delivery once an order has QC-approved quantity.' : undefined}
      />

      <CreateDeliveryModal open={creating} onClose={() => setCreating(false)} onCreated={() => { setCreating(false); reload(); }} />
      <TransitionModal kind={form?.kind} delivery={form?.d} onClose={() => setForm(null)} onSaved={() => { setForm(null); reload(); }} />
      <ConfirmDialog
        open={dialog?.kind === 'cancel'}
        title={`Cancel ${d?.delivery_number || ''}`}
        message="Any reserved finished goods will be released. This cannot be undone."
        confirmLabel="Cancel delivery"
        reason
        reasonLabel="Cancellation reason"
        onClose={closeDialog}
        onConfirm={(reason) => action.run('cancel', () => cancelDelivery(d.id, reason), {
          success: `${d.delivery_number} cancelled`, toastError: false, onSuccess: () => { closeDialog(); reload(); },
        })}
      />
      <ConfirmDialog
        open={dialog?.kind === 'fail'}
        title={`Mark ${d?.delivery_number || ''} as failed`}
        message="A failed delivery is final. The order's quantities become available for a new delivery."
        confirmLabel="Mark failed"
        reason
        reasonLabel="Failure reason"
        onClose={closeDialog}
        onConfirm={(reason) => action.run('fail', () => failDelivery(d.id, { reason, return_to_stock: returnToStock }), {
          success: `${d.delivery_number} marked failed`, toastError: false, onSuccess: () => { closeDialog(); reload(); },
        })}
      >
        <label className="checkbox">
          <input type="checkbox" checked={returnToStock} onChange={(e) => setReturnToStock(e.target.checked)} /> Return goods to stock
        </label>
      </ConfirmDialog>
    </>
  );
}
