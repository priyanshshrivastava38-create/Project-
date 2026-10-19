import { useEffect, useState } from 'react';
import { adjustStock, receiveMaterial } from '../api/inventory';
import { fetchAll, listMaterials, listProducts } from '../api/catalog';
import { listSuppliers } from '../api/suppliers';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useIdempotencyKey } from '../hooks/useIdempotencyKey';
import { useAuth } from '../context/AuthContext';
import { Alert, Button, FormField, Modal, useToast } from '../components';
import { formatNumber, toNumber } from '../utils/format';

export function ReceiveModal({ open, onClose, onDone, warehouses, preset }) {
  const toast = useToast();
  const { can } = useAuth();
  const idem = useIdempotencyKey();
  const materials = useAsync(() => fetchAll(listMaterials, { active: true }), [], { enabled: open });
  const suppliers = useAsync(() => fetchAll(listSuppliers, { status: 'ACTIVE' }), [], { enabled: open && can('suppliers:read') });
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) {
      setForm({
        material_id: preset?.material_id ? String(preset.material_id) : '',
        warehouse_id: preset?.warehouse_id ? String(preset.warehouse_id) : '',
        quantity: '', supplier_id: '', reference: '', notes: '',
      });
      setErrors({}); setFormError(''); idem.reset();
    }
  }, [open, preset, idem]);

  useEffect(() => {
    // Default the supplier to the material's preferred supplier.
    const m = (materials.data || []).find((x) => String(x.id) === form.material_id);
    if (m?.preferred_supplier && !form.supplier_id) setForm((f) => ({ ...f, supplier_id: String(m.preferred_supplier.id) }));
  }, [form.material_id, materials.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.material_id) errs.material_id = 'Select a material';
    if (!form.warehouse_id) errs.warehouse_id = 'Select a warehouse';
    if (!(toNumber(form.quantity) > 0)) errs.quantity = 'Quantity must be greater than 0';
    setErrors(errs); setFormError('');
    if (Object.keys(errs).length) return;
    const body = {
      material_id: Number(form.material_id),
      warehouse_id: Number(form.warehouse_id),
      quantity: form.quantity,
      supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
      reference: form.reference.trim() || null,
      notes: form.notes.trim() || null,
    };
    const key = idem.keyFor(body);
    setPending(true);
    try {
      const txn = await receiveMaterial(body, key);
      idem.reset();
      toast.success(`Received ${formatNumber(body.quantity)} ${txn.balance?.material?.uom || ''} of ${txn.balance?.material?.sku || 'material'}`);
      onDone?.(txn);
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title="Receive material" onClose={onClose} busy={pending}>
      <form onSubmit={submit} className="stack" noValidate>
        <div className="form-grid">
          <FormField label="Material" required error={errors.material_id} className="full">
            <select value={form.material_id || ''} onChange={set('material_id')}>
              <option value="">{materials.loading ? 'Loading…' : 'Select material'}</option>
              {(materials.data || []).map((m) => <option key={m.id} value={m.id}>{m.sku} · {m.name} ({m.uom})</option>)}
            </select>
          </FormField>
          <FormField label="Warehouse" required error={errors.warehouse_id}>
            <select value={form.warehouse_id || ''} onChange={set('warehouse_id')}>
              <option value="">Select warehouse</option>
              {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
            </select>
          </FormField>
          <FormField label="Quantity" required error={errors.quantity}>
            <input type="number" min="0" step="any" value={form.quantity || ''} onChange={set('quantity')} />
          </FormField>
          {can('suppliers:read') ? (
            <FormField label="Supplier" error={errors.supplier_id}>
              <select value={form.supplier_id || ''} onChange={set('supplier_id')}>
                <option value="">None</option>
                {(suppliers.data || []).map((s) => <option key={s.id} value={s.id}>{s.company_name}</option>)}
              </select>
            </FormField>
          ) : null}
          <FormField label="Reference (PO / GRN)" error={errors.reference}>
            <input value={form.reference || ''} onChange={set('reference')} />
          </FormField>
          <FormField label="Notes" className="full" error={errors.notes}>
            <textarea rows={2} value={form.notes || ''} onChange={set('notes')} />
          </FormField>
        </div>
        {materials.error ? <Alert>{errorMessage(materials.error)}</Alert> : null}
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>Record receipt</Button>
        </div>
      </form>
    </Modal>
  );
}

export function AdjustModal({ open, onClose, onDone, warehouses, preset }) {
  const toast = useToast();
  const idem = useIdempotencyKey();
  const [form, setForm] = useState({ item_type: 'MATERIAL' });
  const materials = useAsync(() => fetchAll(listMaterials), [], { enabled: open && form.item_type === 'MATERIAL' });
  const products = useAsync(() => listProducts({ active: true }), [], { enabled: open && form.item_type === 'PRODUCT' });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) {
      setForm({
        item_type: preset?.item_type || 'MATERIAL',
        item_id: preset?.item_id ? String(preset.item_id) : '',
        warehouse_id: preset?.warehouse_id ? String(preset.warehouse_id) : '',
        quantity_delta: '', reason: '',
      });
      setErrors({}); setFormError(''); idem.reset();
    }
  }, [open, preset, idem]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const items = form.item_type === 'MATERIAL' ? materials.data || [] : products.data || [];
  const itemsLoading = form.item_type === 'MATERIAL' ? materials.loading : products.loading;

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.item_id) errs.item_id = 'Select an item';
    if (!form.warehouse_id) errs.warehouse_id = 'Select a warehouse';
    const d = toNumber(form.quantity_delta);
    if (d === null || d === 0) errs.quantity_delta = 'Enter a non-zero quantity (negative to reduce stock)';
    if ((form.reason || '').trim().length < 5) errs.reason = 'Reason must be at least 5 characters';
    setErrors(errs); setFormError('');
    if (Object.keys(errs).length) return;
    const body = {
      item_type: form.item_type,
      item_id: Number(form.item_id),
      warehouse_id: Number(form.warehouse_id),
      quantity_delta: form.quantity_delta,
      reason: form.reason.trim(),
    };
    const key = idem.keyFor(body);
    setPending(true);
    try {
      await adjustStock(body, key);
      idem.reset();
      toast.success('Stock adjustment recorded');
      onDone?.();
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title="Adjust stock" onClose={onClose} busy={pending}>
      <form onSubmit={submit} className="stack" noValidate>
        <div className="form-grid">
          <FormField label="Item type" required error={errors.item_type}>
            <select value={form.item_type} onChange={(e) => setForm((f) => ({ ...f, item_type: e.target.value, item_id: '' }))}>
              <option value="MATERIAL">Material</option>
              <option value="PRODUCT">Product</option>
            </select>
          </FormField>
          <FormField label="Warehouse" required error={errors.warehouse_id}>
            <select value={form.warehouse_id || ''} onChange={set('warehouse_id')}>
              <option value="">Select warehouse</option>
              {(warehouses || []).map((w) => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
            </select>
          </FormField>
          <FormField label={form.item_type === 'MATERIAL' ? 'Material' : 'Product'} required error={errors.item_id} className="full">
            <select value={form.item_id || ''} onChange={set('item_id')}>
              <option value="">{itemsLoading ? 'Loading…' : 'Select item'}</option>
              {items.map((m) => <option key={m.id} value={m.id}>{m.sku} · {m.name} ({m.uom})</option>)}
            </select>
          </FormField>
          <FormField label="Quantity change" required error={errors.quantity_delta} hint="Positive adds stock, negative removes it">
            <input type="number" step="any" value={form.quantity_delta || ''} onChange={set('quantity_delta')} />
          </FormField>
          <FormField label="Reason" required error={errors.reason} className="full" hint="At least 5 characters, e.g. cycle count correction">
            <textarea rows={2} maxLength={500} value={form.reason || ''} onChange={set('reason')} />
          </FormField>
        </div>
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>Record adjustment</Button>
        </div>
      </form>
    </Modal>
  );
}
