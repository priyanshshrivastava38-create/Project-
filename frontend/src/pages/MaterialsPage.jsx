import { useEffect, useState } from 'react';
import { createMaterial, listMaterialCategories, listMaterials, updateMaterial } from '../api/catalog';
import { fetchAll } from '../api/catalog';
import { listSuppliers } from '../api/suppliers';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { useAuth } from '../context/AuthContext';
import {
  Alert, Button, DataTable, FilterSelect, FiltersBar, FormField, Modal, PageHeader, SearchInput, StatusBadge, useToast,
} from '../components';
import { formatNumber, stripZeros, toNumber } from '../utils/format';
import InventoryTabs from './InventoryTabs';

const SKU_RE = /^[A-Z0-9][A-Z0-9\-_.]*$/;

function MaterialModal({ open, material, onClose, onSaved, categories }) {
  const toast = useToast();
  const { can } = useAuth();
  const suppliers = useAsync(() => fetchAll(listSuppliers), [], { enabled: open && can('suppliers:read') });
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(material ? {
      sku: material.sku, name: material.name, category: material.category, grade: material.grade || '', uom: material.uom,
      reorder_level: stripZeros(material.reorder_level), preferred_supplier_id: material.preferred_supplier ? String(material.preferred_supplier.id) : '',
      is_active: material.is_active,
    } : { sku: '', name: '', category: '', grade: '', uom: '', reorder_level: '0', preferred_supplier_id: '', is_active: true });
    setErrors({}); setFormError('');
  }, [open, material]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!material && !SKU_RE.test(form.sku || '')) errs.sku = 'Uppercase letters, digits, - _ . (2–40 chars)';
    if ((form.name || '').trim().length < 2) errs.name = 'Name is required';
    if ((form.category || '').trim().length < 2) errs.category = 'Category is required';
    if (!material && !(form.uom || '').trim()) errs.uom = 'Unit of measure is required';
    if (form.reorder_level !== '' && (toNumber(form.reorder_level) === null || toNumber(form.reorder_level) < 0)) errs.reorder_level = 'Invalid number';
    setErrors(errs); setFormError('');
    if (Object.keys(errs).length) return;
    setPending(true);
    try {
      let saved;
      const common = {
        name: form.name.trim(), category: form.category.trim(), grade: form.grade.trim() || null,
        reorder_level: form.reorder_level === '' ? 0 : form.reorder_level,
        preferred_supplier_id: form.preferred_supplier_id ? Number(form.preferred_supplier_id) : null,
      };
      if (material) saved = await updateMaterial(material.id, { ...common, is_active: form.is_active });
      else saved = await createMaterial({ ...common, sku: form.sku.trim(), uom: form.uom.trim() });
      toast.success(material ? `Material ${saved.sku} updated` : `Material ${saved.sku} created`);
      onSaved(saved);
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title={material ? `Edit ${material.sku}` : 'New material'} onClose={onClose} busy={pending}>
      <form onSubmit={submit} className="stack" noValidate>
        <div className="form-grid">
          <FormField label="SKU" required={!material} error={errors.sku} hint={material ? 'SKU cannot be changed' : 'e.g. SHEET-S275-3MM'}>
            <input value={form.sku || ''} disabled={!!material} onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value.toUpperCase() }))} maxLength={40} />
          </FormField>
          <FormField label="Unit of measure" required={!material} error={errors.uom} hint={material ? 'UoM cannot be changed' : 'e.g. KG, M, EA'}>
            <input value={form.uom || ''} disabled={!!material} onChange={set('uom')} maxLength={12} />
          </FormField>
          <FormField label="Name" required error={errors.name} className="full"><input value={form.name || ''} onChange={set('name')} maxLength={200} /></FormField>
          <FormField label="Category" required error={errors.category}>
            <input value={form.category || ''} onChange={set('category')} list="material-categories" maxLength={60} />
          </FormField>
          <datalist id="material-categories">{(categories || []).map((c) => <option key={c} value={c} />)}</datalist>
          <FormField label="Grade" error={errors.grade}><input value={form.grade || ''} onChange={set('grade')} /></FormField>
          <FormField label="Reorder level" error={errors.reorder_level}><input type="number" min="0" step="any" value={form.reorder_level ?? ''} onChange={set('reorder_level')} /></FormField>
          {can('suppliers:read') ? (
            <FormField label="Preferred supplier" error={errors.preferred_supplier_id}>
              <select value={form.preferred_supplier_id || ''} onChange={set('preferred_supplier_id')}>
                <option value="">None</option>
                {(suppliers.data || []).map((s) => <option key={s.id} value={s.id}>{s.company_name}</option>)}
              </select>
            </FormField>
          ) : null}
          {material ? (
            <label className="checkbox full">
              <input type="checkbox" checked={!!form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
              Active
            </label>
          ) : null}
        </div>
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>{material ? 'Save changes' : 'Create material'}</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function MaterialsPage() {
  const { can } = useAuth();
  const pg = usePagination({ category: '', active: '' });
  const [search, setSearch] = useState('');
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, error, loading, reload } = useAsync(
    () => listMaterials({ ...pg.params, q, active: pg.filters.active === '' ? undefined : pg.filters.active }),
    [pg.page, pg.pageSize, pg.filters.category, pg.filters.active, q],
  );
  const categories = useAsync(() => listMaterialCategories(), []);
  const [editing, setEditing] = useState(null);
  const canWrite = can('materials:write');

  const columns = [
    { key: 'sku', header: 'SKU', sortable: true, render: (r) => <span className="mono">{r.sku}</span> },
    { key: 'name', header: 'Name', sortable: true },
    { key: 'category', header: 'Category', sortable: true },
    { key: 'grade', header: 'Grade', render: (r) => r.grade || '—' },
    { key: 'uom', header: 'UoM' },
    { key: 'reorder_level', header: 'Reorder level', align: 'right', sortable: true, render: (r) => formatNumber(r.reorder_level) },
    { key: 'preferred_supplier', header: 'Preferred supplier', render: (r) => r.preferred_supplier?.company_name || '—' },
    { key: 'is_active', header: 'Status', render: (r) => <StatusBadge status={r.is_active ? 'ACTIVE' : 'INACTIVE'} /> },
    canWrite ? { key: 'actions', header: '', align: 'right', render: (r) => <Button size="sm" variant="ghost" icon="edit" onClick={() => setEditing(r)}>Edit</Button> } : null,
  ].filter(Boolean);

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle="Raw material master data."
        actions={canWrite ? <Button variant="primary" icon="plus" onClick={() => setEditing({})}>New material</Button> : null}
      />
      <InventoryTabs />
      <FiltersBar onReset={() => { setSearch(''); pg.resetFilters(); }}>
        <SearchInput value={search} onChange={setSearch} placeholder="SKU or name…" />
        <FilterSelect label="Category" value={pg.filters.category} onChange={(v) => pg.setFilter('category', v)} options={categories.data || []} />
        <FilterSelect label="Status" value={pg.filters.active} onChange={(v) => pg.setFilter('active', v)} options={[{ value: 'true', label: 'Active' }, { value: 'false', label: 'Inactive' }]} />
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
        emptyTitle="No materials match"
      />
      <MaterialModal
        open={editing !== null}
        material={editing && editing.id ? editing : null}
        categories={categories.data}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); reload(); categories.reload(); }}
      />
    </>
  );
}
