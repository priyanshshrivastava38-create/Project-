import { useEffect, useState } from 'react';
import { createSupplier, listSuppliers, updateSupplier } from '../api/suppliers';
import { fetchAll, listMaterials } from '../api/catalog';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { useAction } from '../hooks/useAction';
import { useAuth } from '../context/AuthContext';
import {
  Alert, Button, ConfirmDialog, DataTable, FilterSelect, FiltersBar, FormField, Modal, PageHeader, SearchInput,
  StatusBadge, useToast,
} from '../components';

const EMPTY = { company_name: '', contact_person: '', email: '', phone: '', address: '', material_ids: [] };

function SupplierFormModal({ open, supplier, onClose, onSaved, canLoadMaterials }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);
  const [matFilter, setMatFilter] = useState('');
  const materials = useAsync(() => fetchAll(listMaterials, { active: true }), [], { enabled: open && canLoadMaterials });

  useEffect(() => {
    if (open) {
      setForm(supplier ? {
        company_name: supplier.company_name || '', contact_person: supplier.contact_person || '', email: supplier.email || '',
        phone: supplier.phone || '', address: supplier.address || '', material_ids: (supplier.materials || []).map((m) => m.id),
      } : EMPTY);
      setErrors({}); setFormError(''); setMatFilter('');
    }
  }, [open, supplier]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const toggleMat = (mid) => setForm((f) => ({
    ...f, material_ids: f.material_ids.includes(mid) ? f.material_ids.filter((x) => x !== mid) : [...f.material_ids, mid],
  }));

  const submit = async (e) => {
    e.preventDefault();
    if (form.company_name.trim().length < 2) { setErrors({ company_name: 'Company name must be at least 2 characters' }); return; }
    setPending(true); setErrors({}); setFormError('');
    const body = {
      company_name: form.company_name.trim(),
      contact_person: form.contact_person.trim() || null,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      address: form.address.trim() || null,
      material_ids: form.material_ids,
    };
    try {
      const saved = supplier ? await updateSupplier(supplier.id, body) : await createSupplier(body);
      toast.success(supplier ? `Supplier ${saved.code} updated` : `Supplier ${saved.code} created`);
      onSaved(saved);
    } catch (err) {
      const fe = fieldErrors(err);
      setErrors(fe);
      setFormError(Object.keys(fe).length ? err.message : errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  const mats = (materials.data || []).filter((m) => !matFilter || `${m.sku} ${m.name}`.toLowerCase().includes(matFilter.toLowerCase()));

  return (
    <Modal open={open} title={supplier ? `Edit ${supplier.company_name}` : 'New supplier'} onClose={onClose} busy={pending} size="lg">
      <form onSubmit={submit} className="stack" noValidate>
        <div className="form-grid">
          <FormField label="Company name" required error={errors.company_name} className="full">
            <input value={form.company_name} onChange={set('company_name')} maxLength={200} />
          </FormField>
          <FormField label="Contact person" error={errors.contact_person}><input value={form.contact_person} onChange={set('contact_person')} /></FormField>
          <FormField label="Email" error={errors.email}><input type="email" value={form.email} onChange={set('email')} /></FormField>
          <FormField label="Phone" error={errors.phone}><input value={form.phone} onChange={set('phone')} /></FormField>
          <FormField label="Address" error={errors.address}><input value={form.address} onChange={set('address')} /></FormField>
        </div>
        <fieldset className="card" style={{ padding: 12 }}>
          <legend className="field-label" style={{ padding: '0 4px' }}>Materials supplied ({form.material_ids.length} selected)</legend>
          {!canLoadMaterials ? <p className="muted small">You do not have permission to list materials.</p> : materials.error ? (
            <Alert>{errorMessage(materials.error)}</Alert>
          ) : materials.loading ? <p className="muted small">Loading materials…</p> : (
            <>
              <input className="control" placeholder="Filter materials…" aria-label="Filter materials" value={matFilter} onChange={(e) => setMatFilter(e.target.value)} style={{ marginBottom: 8 }} />
              <div style={{ maxHeight: 200, overflowY: 'auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 6 }}>
                {mats.map((m) => (
                  <label key={m.id} className="checkbox">
                    <input type="checkbox" checked={form.material_ids.includes(m.id)} onChange={() => toggleMat(m.id)} />
                    <span><span className="mono">{m.sku}</span> <span className="muted small">{m.name}</span></span>
                  </label>
                ))}
                {!mats.length ? <span className="muted small">No materials match.</span> : null}
              </div>
            </>
          )}
          {errors.material_ids ? <div className="field-err">{errors.material_ids}</div> : null}
        </fieldset>
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>{supplier ? 'Save changes' : 'Create supplier'}</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function SuppliersPage() {
  const { can } = useAuth();
  const action = useAction();
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('company_name');
  const pg = usePagination({ status: '' });
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, error, loading, reload } = useAsync(
    () => listSuppliers({ ...pg.params, q, sort }),
    [pg.page, pg.pageSize, pg.filters.status, q, sort],
  );
  const [editing, setEditing] = useState(null);
  const [deactivating, setDeactivating] = useState(null);
  const canWrite = can('suppliers:write');

  const columns = [
    { key: 'code', header: 'Code', sortable: true, render: (r) => <span className="mono">{r.code}</span> },
    { key: 'company_name', header: 'Company', sortable: true, render: (r) => <strong>{r.company_name}</strong> },
    { key: 'contact_person', header: 'Contact', render: (r) => (
      <div><div>{r.contact_person || '—'}</div><div className="small muted">{[r.email, r.phone].filter(Boolean).join(' · ')}</div></div>
    ) },
    { key: 'materials', header: 'Materials supplied', render: (r) => (
      r.materials?.length ? <div className="chip-list">{r.materials.map((m) => <span key={m.id} className="chip" title={m.name}>{m.sku}</span>)}</div> : <span className="muted">—</span>
    ) },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
    canWrite ? { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <Button size="sm" variant="ghost" icon="edit" onClick={() => setEditing(r)}>Edit</Button>
        {r.status === 'ACTIVE'
          ? <Button size="sm" variant="danger-outline" onClick={() => setDeactivating(r)}>Deactivate</Button>
          : <Button size="sm" loading={action.isPending(`a-${r.id}`)} onClick={() => action.run(`a-${r.id}`, () => updateSupplier(r.id, { status: 'ACTIVE' }), { success: `${r.company_name} reactivated`, onSuccess: reload })}>Activate</Button>}
      </div>
    ) } : null,
  ].filter(Boolean);

  return (
    <>
      <PageHeader
        title="Suppliers"
        subtitle="Vendors of raw materials."
        actions={canWrite ? <Button variant="primary" icon="plus" onClick={() => setEditing({})}>New supplier</Button> : null}
      />
      <FiltersBar>
        <SearchInput value={search} onChange={setSearch} placeholder="Search suppliers…" />
        <FilterSelect label="Status" value={pg.filters.status} onChange={(v) => pg.setFilter('status', v)} options={['ACTIVE', 'INACTIVE']} />
      </FiltersBar>
      <DataTable
        columns={columns}
        rows={data?.items}
        loading={loading}
        error={error}
        onRetry={reload}
        sort={sort}
        onSortChange={(s) => { setSort(s || 'company_name'); pg.setPage(1); }}
        page={pg.page}
        pageSize={pg.pageSize}
        total={data?.total}
        onPageChange={pg.setPage}
        onPageSizeChange={pg.setPageSize}
        emptyTitle="No suppliers match"
      />
      <SupplierFormModal
        open={editing !== null}
        supplier={editing && editing.id ? editing : null}
        canLoadMaterials={can('products:read')}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); reload(); }}
      />
      <ConfirmDialog
        open={!!deactivating}
        title="Deactivate supplier"
        message={deactivating ? `Deactivate ${deactivating.company_name}?` : ''}
        confirmLabel="Deactivate"
        onClose={() => setDeactivating(null)}
        onConfirm={() => action.run('deact', () => updateSupplier(deactivating.id, { status: 'INACTIVE' }), {
          success: `${deactivating.company_name} deactivated`, toastError: false,
          onSuccess: () => { setDeactivating(null); reload(); },
        })}
      />
    </>
  );
}
