import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { cancelOrder, confirmOrder, getOrder, rejectOrder } from '../api/orders';
import { useAsync } from '../hooks/useAsync';
import { useAction } from '../hooks/useAction';
import { useAuth } from '../context/AuthContext';
import {
  Button, Card, ConfirmDialog, ErrorState, KeyValue, PageHeader, ProgressBar, Spinner, StatusBadge, Timeline,
} from '../components';
import CreateJobModal from '../components/CreateJobModal';
import CreateDeliveryModal from '../components/CreateDeliveryModal';
import { formatDate, formatMoney, formatNumber, stripZeros, toNumber } from '../utils/format';
import { statusTone } from '../utils/status';

const PRODUCTION_ORDER_STATES = ['CONFIRMED', 'IN_PRODUCTION', 'PARTIALLY_FULFILLED'];

export default function OrderDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { can } = useAuth();
  const action = useAction();
  const { data: o, error, reload } = useAsync(() => getOrder(id), [id]);
  const [dialog, setDialog] = useState(null); // 'cancel' | 'reject'
  const [jobLine, setJobLine] = useState(null);
  const [deliveryOpen, setDeliveryOpen] = useState(false);

  if (error && !o) return <ErrorState error={error} onRetry={reload} />;
  if (!o) return <Spinner />;

  const s = o.status;
  const canWrite = can('orders:write');
  const canCancel = canWrite && (['DRAFT', 'CONFIRMED'].includes(s) || (s === 'IN_PRODUCTION' && can('orders:cancel_in_production')));
  const canProduce = can('production:write') && PRODUCTION_ORDER_STATES.includes(s);
  const canDeliver = can('deliveries:write') && ['IN_PRODUCTION', 'PARTIALLY_FULFILLED'].includes(s);

  const timeline = [...o.history].reverse().map((h) => ({
    status: h.to_status, from: h.from_status, note: h.reason, by: h.changed_by?.full_name, at: h.changed_at, tone: statusTone(h.to_status),
  }));

  return (
    <>
      <PageHeader
        title={o.order_number}
        meta={<StatusBadge status={s} />}
        subtitle={(
          <>
            {can('customers:read') ? <Link to={`/customers/${o.customer.id}`}>{o.customer.company_name}</Link> : o.customer.company_name}
            {' · '}{o.customer.code}
          </>
        )}
        breadcrumbs={[{ label: 'Orders', to: '/orders' }, { label: o.order_number }]}
        actions={(
          <>
            {canWrite && s === 'DRAFT' ? <Button icon="edit" onClick={() => navigate(`/orders/${o.id}/edit`)}>Edit</Button> : null}
            {canWrite && s === 'DRAFT' ? (
              <Button variant="primary" icon="check" loading={action.isPending('confirm')} disabled={action.anyPending}
                onClick={() => action.run('confirm', () => confirmOrder(o.id), { success: `${o.order_number} confirmed`, onSuccess: reload })}>
                Confirm order
              </Button>
            ) : null}
            {canDeliver ? <Button icon="deliveries" onClick={() => setDeliveryOpen(true)}>Create delivery</Button> : null}
            {can('orders:reject') && s === 'DRAFT' ? <Button variant="danger-outline" onClick={() => setDialog('reject')}>Reject</Button> : null}
            {canCancel ? <Button variant="danger-outline" onClick={() => setDialog('cancel')}>Cancel order</Button> : null}
          </>
        )}
      />

      <Card title="Summary">
        <KeyValue items={[
          ['Order date', formatDate(o.order_date)],
          ['Required date', formatDate(o.required_date)],
          ['Currency', o.currency],
          ['Tax rate', `${stripZeros(o.tax_rate)}%`],
          ['Subtotal', formatMoney(o.subtotal, o.currency)],
          ['Tax', formatMoney(o.tax_amount, o.currency)],
          ['Total', <strong key="t">{formatMoney(o.total, o.currency)}</strong>],
          ['Created by', o.created_by?.full_name],
          ['Notes', o.notes],
        ]} />
      </Card>

      <Card title="Line items & progress" subtitle="Ordered → planned → QC-approved → allocated to deliveries → delivered" padded={false}>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>#</th><th>Product</th><th className="num">Qty</th><th className="num">Unit price</th><th className="num">Line total</th>
                <th className="num">Planned</th><th className="num">QC approved</th><th className="num">Allocated</th><th className="num">Delivered</th>
                <th>Progress</th>{canProduce ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {o.item_progress.map((l) => {
                const qty = toNumber(l.quantity) || 0;
                const unplanned = qty - (toNumber(l.planned_quantity) || 0);
                return (
                  <tr key={l.id}>
                    <td>{l.line_number}</td>
                    <td><span className="mono">{l.sku}</span><div className="small muted">{l.description}</div></td>
                    <td className="num">{formatNumber(l.quantity)}</td>
                    <td className="num">{formatMoney(l.unit_price, o.currency)}</td>
                    <td className="num">{formatMoney(l.line_total, o.currency)}</td>
                    <td className="num">{formatNumber(l.planned_quantity)}</td>
                    <td className="num">{formatNumber(l.approved_quantity)}</td>
                    <td className="num">{formatNumber(l.allocated_to_deliveries)}</td>
                    <td className="num">{formatNumber(l.delivered_quantity)}</td>
                    <td className="progress-cell">
                      <ProgressBar value={toNumber(l.approved_quantity)} max={qty} tone="teal" label="QC approved" />
                      <div style={{ height: 4 }} />
                      <ProgressBar value={toNumber(l.delivered_quantity)} max={qty} tone="green" label="Delivered" />
                      <div className="progress-legend"><span>QC {Math.round(((toNumber(l.approved_quantity) || 0) / (qty || 1)) * 100)}%</span><span>Delivered {Math.round(((toNumber(l.delivered_quantity) || 0) / (qty || 1)) * 100)}%</span></div>
                    </td>
                    {canProduce ? (
                      <td>
                        <Button size="sm" icon="production" onClick={() => setJobLine(l)} title={unplanned <= 0 ? 'Line is fully planned' : undefined}>
                          Create job
                        </Button>
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid-2 section-gap">
        <Card title="Production jobs" padded={false}>
          {o.jobs.length ? (
            <table className="table table-dense">
              <thead><tr><th>Job</th><th>Status</th><th className="num">Planned</th><th className="num">Approved</th></tr></thead>
              <tbody>
                {o.jobs.map((j) => (
                  <tr key={j.id}>
                    <td>{can('production:read') ? <Link to={`/production/jobs/${j.id}`}>{j.job_number}</Link> : j.job_number}</td>
                    <td><StatusBadge status={j.status} /></td>
                    <td className="num">{formatNumber(j.planned_quantity)}</td>
                    <td className="num">{formatNumber(j.approved_quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted card-body">No production jobs yet.</p>}
        </Card>
        <Card title="Deliveries" padded={false}>
          {o.deliveries.length ? (
            <table className="table table-dense">
              <thead><tr><th>Delivery</th><th>Status</th></tr></thead>
              <tbody>
                {o.deliveries.map((d) => (
                  <tr key={d.id}>
                    <td>{can('deliveries:read') ? <Link to={`/deliveries?highlight=${d.id}&q=${encodeURIComponent(d.delivery_number)}`}>{d.delivery_number}</Link> : d.delivery_number}</td>
                    <td><StatusBadge status={d.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted card-body">No deliveries yet.</p>}
        </Card>
      </div>

      <Card title="Status history">
        <Timeline entries={timeline} />
      </Card>

      <ConfirmDialog
        open={dialog === 'cancel'}
        title={`Cancel ${o.order_number}`}
        message={s === 'IN_PRODUCTION' ? 'This order is in production. Open jobs will be cancelled and reserved material released. This cannot be undone.' : 'Cancelling an order cannot be undone.'}
        confirmLabel="Cancel order"
        reason
        reasonLabel="Cancellation reason"
        onClose={() => setDialog(null)}
        onConfirm={(reason) => action.run('cancel', () => cancelOrder(o.id, reason), {
          success: `${o.order_number} cancelled`, toastError: false, onSuccess: () => { setDialog(null); reload(); },
        })}
      />
      <ConfirmDialog
        open={dialog === 'reject'}
        title={`Reject ${o.order_number}`}
        message="Rejecting a draft order is final."
        confirmLabel="Reject order"
        reason
        reasonLabel="Rejection reason"
        onClose={() => setDialog(null)}
        onConfirm={(reason) => action.run('reject', () => rejectOrder(o.id, reason), {
          success: `${o.order_number} rejected`, toastError: false, onSuccess: () => { setDialog(null); reload(); },
        })}
      />
      <CreateJobModal open={!!jobLine} line={jobLine} onClose={() => setJobLine(null)} onCreated={() => { setJobLine(null); reload(); }} />
      <CreateDeliveryModal open={deliveryOpen} orderId={o.id} onClose={() => setDeliveryOpen(false)} onCreated={() => { setDeliveryOpen(false); reload(); }} />
    </>
  );
}
