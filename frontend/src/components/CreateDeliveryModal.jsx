import { useEffect, useState } from 'react';
import { createDelivery, listDispatchable } from '../api/deliveries';
import { listWarehouses } from '../api/catalog';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../context/AuthContext';
import Modal from './Modal';
import Button from './Button';
import FormField from './FormField';
import { Alert, EmptyState } from './States';
import Spinner from './Spinner';
import { useToast } from './Toast';
import { formatDate, formatNumber, stripZeros, toNumber } from '../utils/format';

/** Create a delivery for one order; quantities are limited to what is dispatchable (QC-approved, not yet allocated). */
export default function CreateDeliveryModal({ open, orderId, onClose, onCreated }) {
  const toast = useToast();
  const { can } = useAuth();
  const dispatchable = useAsync(() => listDispatchable(), [open], { enabled: open });
  const warehouses = useAsync(() => listWarehouses(), [], { enabled: open && can('inventory:read') });
  const [selectedOrder, setSelectedOrder] = useState('');
  const [qty, setQty] = useState({});
  const [meta, setMeta] = useState({ planned_dispatch_date: '', carrier: '', warehouse_id: '', notes: '' });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) {
      setSelectedOrder(orderId ? String(orderId) : '');
      setQty({}); setErrors({}); setFormError('');
      setMeta({ planned_dispatch_date: '', carrier: '', warehouse_id: '', notes: '' });
    }
  }, [open, orderId]);

  const orders = dispatchable.data || [];
  const order = orders.find((o) => String(o.order_id) === selectedOrder);

  useEffect(() => {
    if (order) setQty(Object.fromEntries(order.lines.map((l) => [l.order_item_id, stripZeros(l.dispatchable)])));
  }, [order]);

  const submit = async (e) => {
    e.preventDefault();
    setFormError('');
    const errs = {};
    if (!order) errs.order = 'Select an order with dispatchable quantity';
    const items = [];
    (order?.lines || []).forEach((l) => {
      const v = qty[l.order_item_id];
      if (v === undefined || v === '' || toNumber(v) === 0) return;
      const n = toNumber(v);
      if (n === null || n < 0) errs[`q${l.order_item_id}`] = 'Invalid quantity';
      else if (n > toNumber(l.dispatchable)) errs[`q${l.order_item_id}`] = `Max ${formatNumber(l.dispatchable)}`;
      else items.push({ order_item_id: l.order_item_id, quantity: v });
    });
    if (order && !items.length && !Object.keys(errs).length) errs.items = 'Enter a quantity for at least one line';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setPending(true);
    try {
      const d = await createDelivery({
        order_id: order.order_id,
        warehouse_id: meta.warehouse_id ? Number(meta.warehouse_id) : null,
        planned_dispatch_date: meta.planned_dispatch_date || null,
        carrier: meta.carrier.trim() || null,
        notes: meta.notes.trim() || null,
        items,
      });
      toast.success(`Delivery ${d.delivery_number} created`);
      onCreated?.(d);
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title="Create delivery" onClose={onClose} busy={pending} size="lg">
      {dispatchable.error ? <Alert>{errorMessage(dispatchable.error)}</Alert> : dispatchable.loading ? <Spinner /> : !orders.length ? (
        <EmptyState title="Nothing ready to ship" message="No order has QC-approved quantity that is not already allocated to a delivery." icon="deliveries" />
      ) : (
        <form onSubmit={submit} className="stack" noValidate>
          <FormField label="Order" required error={errors.order}>
            <select value={selectedOrder} onChange={(e) => setSelectedOrder(e.target.value)} disabled={Boolean(orderId)}>
              <option value="">Select order</option>
              {orders.map((o) => <option key={o.order_id} value={o.order_id}>{o.order_number} · {o.customer_name}</option>)}
            </select>
          </FormField>
          {orderId && !order ? <Alert tone="warning">This order has no dispatchable quantity right now (nothing QC-approved and unallocated).</Alert> : null}
          {order ? (
            <>
              <p className="muted small">Required by {formatDate(order.required_date)}. Quantities cannot exceed the dispatchable amount.</p>
              {errors.items ? <Alert>{errors.items}</Alert> : null}
              <div className="table-scroll">
                <table className="table table-dense">
                  <thead><tr><th>Line</th><th className="num">Ordered</th><th className="num">QC approved</th><th className="num">Allocated</th><th className="num">Dispatchable</th><th style={{ width: 140 }}>Ship qty</th></tr></thead>
                  <tbody>
                    {order.lines.map((l) => (
                      <tr key={l.order_item_id}>
                        <td><span className="mono">{l.sku}</span><div className="small muted">{l.description}</div></td>
                        <td className="num">{formatNumber(l.ordered)}</td>
                        <td className="num">{formatNumber(l.approved)}</td>
                        <td className="num">{formatNumber(l.allocated)}</td>
                        <td className="num"><strong>{formatNumber(l.dispatchable)}</strong></td>
                        <td>
                          <input className="control" type="number" min="0" max={toNumber(l.dispatchable)} step="any" aria-label={`Ship quantity for ${l.sku}`}
                            value={qty[l.order_item_id] ?? ''} onChange={(e) => setQty((q) => ({ ...q, [l.order_item_id]: e.target.value }))} />
                          {errors[`q${l.order_item_id}`] ? <div className="field-err">{errors[`q${l.order_item_id}`]}</div> : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="form-grid">
                <FormField label="Planned dispatch date" error={errors.planned_dispatch_date}>
                  <input type="date" value={meta.planned_dispatch_date} onChange={(e) => setMeta((m) => ({ ...m, planned_dispatch_date: e.target.value }))} />
                </FormField>
                <FormField label="Carrier" error={errors.carrier}>
                  <input value={meta.carrier} onChange={(e) => setMeta((m) => ({ ...m, carrier: e.target.value }))} />
                </FormField>
                {warehouses.data ? (
                  <FormField label="Ship from warehouse" hint="Blank = default finished-goods warehouse" error={errors.warehouse_id}>
                    <select value={meta.warehouse_id} onChange={(e) => setMeta((m) => ({ ...m, warehouse_id: e.target.value }))}>
                      <option value="">Default</option>
                      {warehouses.data.map((w) => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
                    </select>
                  </FormField>
                ) : null}
                <FormField label="Notes" error={errors.notes}>
                  <input value={meta.notes} onChange={(e) => setMeta((m) => ({ ...m, notes: e.target.value }))} />
                </FormField>
              </div>
            </>
          ) : null}
          {formError ? <Alert>{formError}</Alert> : null}
          <div className="modal-actions">
            <Button onClick={onClose} disabled={pending}>Cancel</Button>
            <Button type="submit" variant="primary" loading={pending} disabled={!order}>Create delivery</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
