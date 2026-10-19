import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { createOrder, getOrder, updateOrder } from '../api/orders';
import { listCustomers } from '../api/customers';
import { fetchAll, listProducts } from '../api/catalog';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import {
  Alert, Button, Card, ErrorState, FormField, Icon, PageHeader, Spinner, useToast,
} from '../components';
import { formatMoney, isoDate, stripZeros, toNumber } from '../utils/format';

let lineSeq = 0;
const newLine = (product) => ({
  key: ++lineSeq,
  product_id: product ? String(product.id) : '',
  quantity: '',
  unit_price: product ? stripZeros(product.unit_price) : '',
});

const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100;

/** Client-side estimate only; the server calculates the authoritative totals. */
export function computeEstimate(lines, taxRate) {
  const lineTotals = lines.map((l) => {
    const q = toNumber(l.quantity);
    const p = toNumber(l.unit_price);
    return q !== null && p !== null ? round2(q * p) : 0;
  });
  const subtotal = round2(lineTotals.reduce((a, b) => a + b, 0));
  const rate = toNumber(taxRate) || 0;
  const tax = round2((subtotal * rate) / 100);
  return { lineTotals, subtotal, tax, total: round2(subtotal + tax) };
}

export default function OrderFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const toast = useToast();
  const [search] = useSearchParams();

  const customers = useAsync(() => fetchAll(listCustomers, { status: 'ACTIVE' }), []);
  const products = useAsync(() => listProducts({ active: true }), []);
  const existing = useAsync(() => getOrder(id), [id], { enabled: isEdit });

  const [form, setForm] = useState({
    customer_id: search.get('customer_id') || '',
    order_date: isoDate(),
    required_date: '',
    currency: 'USD',
    tax_rate: '',
    notes: '',
  });
  const [lines, setLines] = useState(() => [newLine()]);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);
  const loadedRef = useRef(false);

  useEffect(() => {
    const o = existing.data;
    if (!o || loadedRef.current) return;
    loadedRef.current = true;
    setForm({
      customer_id: String(o.customer.id),
      order_date: o.order_date,
      required_date: o.required_date || '',
      currency: o.currency,
      tax_rate: stripZeros(o.tax_rate),
      notes: o.notes || '',
    });
    setLines(o.items.map((it) => ({
      key: ++lineSeq, product_id: String(it.product_id), quantity: stripZeros(it.quantity), unit_price: stripZeros(it.unit_price),
    })));
  }, [existing.data]);

  const productMap = useMemo(() => new Map((products.data || []).map((p) => [String(p.id), p])), [products.data]);
  const estimate = computeEstimate(lines, form.tax_rate);

  const setField = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const updateLine = (key, patch) => setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const onProduct = (key, pid) => {
    const p = productMap.get(pid);
    updateLine(key, { product_id: pid, unit_price: p ? stripZeros(p.unit_price) : '' });
  };

  const validate = () => {
    const e = {};
    if (!form.customer_id) e.customer_id = 'Select a customer';
    if (!/^[A-Z]{3}$/.test(form.currency)) e.currency = 'Use a 3-letter currency code, e.g. USD';
    if (form.tax_rate !== '' && (toNumber(form.tax_rate) === null || toNumber(form.tax_rate) < 0)) e.tax_rate = 'Enter a valid tax rate';
    const filled = lines.filter((l) => l.product_id);
    if (!filled.length) e.lines = 'Add at least one line item with a product';
    lines.forEach((l, i) => {
      if (!l.product_id) return;
      const q = toNumber(l.quantity);
      if (q === null || q <= 0) e[`items.${i}.quantity`] = 'Quantity must be greater than 0';
      const p = toNumber(l.unit_price);
      if (l.unit_price !== '' && (p === null || p < 0)) e[`items.${i}.unit_price`] = 'Invalid price';
    });
    return e;
  };

  const submit = async (ev) => {
    ev.preventDefault();
    setFormError('');
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length) return;
    const items = lines.filter((l) => l.product_id).map((l) => ({
      product_id: Number(l.product_id),
      quantity: l.quantity,
      unit_price: l.unit_price === '' ? null : l.unit_price,
    }));
    const body = {
      customer_id: Number(form.customer_id),
      required_date: form.required_date || null,
      currency: form.currency,
      tax_rate: form.tax_rate === '' ? null : form.tax_rate,
      notes: form.notes.trim() || null,
      items,
    };
    if (!isEdit) body.order_date = form.order_date || null;
    setPending(true);
    try {
      const saved = isEdit ? await updateOrder(id, body) : await createOrder(body);
      toast.success(isEdit ? `Order ${saved.order_number} updated` : `Order ${saved.order_number} created as draft`);
      navigate(`/orders/${saved.id}`);
    } catch (err) {
      const fe = fieldErrors(err);
      setErrors(fe);
      setFormError(errorMessage(err));
      setPending(false);
    }
  };

  if (isEdit && existing.error) return <ErrorState error={existing.error} onRetry={existing.reload} />;
  if (isEdit && !existing.data) return <Spinner />;
  const notDraft = isEdit && existing.data.status !== 'DRAFT';
  const loadError = customers.error || products.error;

  return (
    <>
      <PageHeader
        title={isEdit ? `Edit ${existing.data.order_number}` : 'New sales order'}
        breadcrumbs={[{ label: 'Orders', to: '/orders' }, { label: isEdit ? existing.data.order_number : 'New' }]}
      />
      {notDraft ? <Alert tone="warning" title="This order can no longer be edited">Only DRAFT orders can be edited. Current status: {existing.data.status}.</Alert> : null}
      {loadError ? <Alert>{errorMessage(loadError)}</Alert> : null}
      <form onSubmit={submit} noValidate aria-label="Order form">
        <fieldset disabled={notDraft || pending} style={{ border: 0, padding: 0, margin: 0 }}>
          <Card title="Order details">
            <div className="form-grid">
              <FormField label="Customer" required error={errors.customer_id}>
                <select value={form.customer_id} onChange={setField('customer_id')}>
                  <option value="">{customers.loading ? 'Loading…' : 'Select customer'}</option>
                  {(customers.data || []).map((c) => <option key={c.id} value={c.id}>{c.company_name} ({c.code})</option>)}
                  {isEdit && existing.data && !(customers.data || []).some((c) => String(c.id) === form.customer_id) ? (
                    <option value={existing.data.customer.id}>{existing.data.customer.company_name}</option>
                  ) : null}
                </select>
              </FormField>
              {!isEdit ? (
                <FormField label="Order date" error={errors.order_date}>
                  <input type="date" value={form.order_date} onChange={setField('order_date')} />
                </FormField>
              ) : <div />}
              <FormField label="Required date" error={errors.required_date}>
                <input type="date" value={form.required_date} onChange={setField('required_date')} />
              </FormField>
              <div className="grid-2">
                <FormField label="Currency" required error={errors.currency}>
                  <input value={form.currency} maxLength={3} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))} />
                </FormField>
                <FormField label="Tax rate (%)" error={errors.tax_rate} hint="Blank = server default">
                  <input type="number" min="0" step="0.01" value={form.tax_rate} onChange={setField('tax_rate')} />
                </FormField>
              </div>
              <FormField label="Notes" error={errors.notes} className="full">
                <textarea rows={2} value={form.notes} onChange={setField('notes')} />
              </FormField>
            </div>
          </Card>

          <Card
            title="Line items"
            actions={<Button size="sm" icon="plus" onClick={() => setLines((ls) => [...ls, newLine()])}>Add line</Button>}
          >
            {errors.lines || errors.items ? <Alert>{errors.lines || errors.items}</Alert> : null}
            <div className="table-scroll">
              <table className="table lines-table">
                <thead>
                  <tr><th style={{ width: '45%' }}>Product</th><th>Quantity</th><th>Unit price</th><th className="num">Est. line total</th><th /></tr>
                </thead>
                <tbody>
                  {lines.map((l, i) => {
                    const p = productMap.get(l.product_id);
                    return (
                      <tr key={l.key}>
                        <td>
                          <select className="control" aria-label={`Product for line ${i + 1}`} value={l.product_id} onChange={(e) => onProduct(l.key, e.target.value)}>
                            <option value="">{products.loading ? 'Loading…' : 'Select product'}</option>
                            {(products.data || []).map((pr) => <option key={pr.id} value={pr.id}>{pr.sku} · {pr.name}</option>)}
                          </select>
                          {errors[`items.${i}.product_id`] ? <div className="field-err">{errors[`items.${i}.product_id`]}</div> : null}
                        </td>
                        <td>
                          <input className="control" type="number" min="0" step="any" aria-label={`Quantity for line ${i + 1}`} value={l.quantity} onChange={(e) => updateLine(l.key, { quantity: e.target.value })} />
                          {p ? <div className="field-hint">{p.uom}</div> : null}
                          {errors[`items.${i}.quantity`] ? <div className="field-err">{errors[`items.${i}.quantity`]}</div> : null}
                        </td>
                        <td>
                          <input className="control" type="number" min="0" step="0.01" aria-label={`Unit price for line ${i + 1}`} value={l.unit_price} onChange={(e) => updateLine(l.key, { unit_price: e.target.value })} />
                          {p && l.unit_price !== stripZeros(p.unit_price) ? <div className="field-hint">List price {formatMoney(p.unit_price, form.currency)}</div> : null}
                          {errors[`items.${i}.unit_price`] ? <div className="field-err">{errors[`items.${i}.unit_price`]}</div> : null}
                        </td>
                        <td className="num">{formatMoney(estimate.lineTotals[i], form.currency)}</td>
                        <td>
                          <button type="button" className="icon-btn" aria-label={`Remove line ${i + 1}`} onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))}>
                            <Icon name="close" size={16} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {!lines.length ? <tr><td colSpan={5} className="muted">No lines. Add at least one product.</td></tr> : null}
                </tbody>
              </table>
            </div>
            <div className="row-between" style={{ marginTop: 16, alignItems: 'flex-start' }}>
              <p className="muted small" style={{ maxWidth: 420 }}>
                <Icon name="info" size={14} /> Estimate only. The server calculates the final subtotal, tax and total when the order is saved.
              </p>
              <div className="estimate" aria-label="Estimated totals">
                <span>Subtotal (est.): <strong data-testid="est-subtotal">{formatMoney(estimate.subtotal, form.currency)}</strong></span>
                <span>Tax (est.{form.tax_rate === '' ? ', server default rate not included' : ` @ ${form.tax_rate}%`}): <strong>{formatMoney(estimate.tax, form.currency)}</strong></span>
                <span className="total">Estimated total: <span data-testid="est-total">{formatMoney(estimate.total, form.currency)}</span></span>
              </div>
            </div>
          </Card>
        </fieldset>
        {formError ? <div className="section-gap"><Alert>{formError}</Alert></div> : null}
        <div className="row section-gap" style={{ justifyContent: 'flex-end' }}>
          <Button onClick={() => navigate(isEdit ? `/orders/${id}` : '/orders')} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending} disabled={notDraft}>{isEdit ? 'Save changes' : 'Create draft order'}</Button>
        </div>
      </form>
    </>
  );
}
