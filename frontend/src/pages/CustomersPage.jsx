import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createCustomer, listCustomers, updateCustomer } from '../api/customers';
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
import { formatDate } from '../utils/format';

const EMPTY = { company_name: '', contact_person: '', email: '', phone: '', billing_address: '', shipping_address: '', tax_id: '' };

function nullify(obj) {
  const out = {};
  Object.entries(obj).forEach(([k, v]) => { out[k] = typeof v === 'string' && v.trim() === '' ? null : (typeof v === 'string' ? v.trim() : v); });
  return out;
}

export function CustomerFormModal({ open, customer, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(customer ? Object.fromEntries(Object.keys(EMPTY).map((k) => [k, customer[k] ?? ''])) : EMPTY);
      setErrors({});
      setFormError('');
    }
  }, [open, customer]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (form.company_name.trim().length < 2) { setErrors({ company_name: 'Company name must be at least 2 characters' }); return; }
    setPending(true);
    setErrors({});
    setFormError('');
    try {
      const body = nullify(form);
      const saved = customer ? await updateCustomer(customer.id, body) : await createCustomer(body);
      toast.success(customer ? `Customer ${saved.code} updated` : `Customer ${saved.code} created`);
      onSaved(saved);
    } catch (err) {
      const fe = fieldErrors(err);
      setErrors(fe);
      if (!Object.keys(fe).length) setFormError(errorMessage(err)); else setFormError(err.message);
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title={customer ? `Edit ${customer.company_name}` : 'New customer'} onClose={onClose} busy={pending}>
      <form onSubmit={submit} className="stack" noValidate>
        <div className="form-grid">
          <FormField label="Company name" required error={errors.company_name} className="full">
            <input value={form.company_name} onChange={set('company_name')} maxLength={200} />
          </FormField>
          <FormField label="Contact person" error={errors.contact_person}><input value={form.contact_person} onChange={set('contact_person')} /></FormField>
          <FormField label="Email" error={errors.email}><input type="email" value={form.email} onChange={set('email')} /></FormField>
          <FormField label="Phone" error={errors.phone}><input value={form.phone} onChange={set('phone')} /></FormField>
          <FormField label="Tax ID" error={errors.tax_id}><input value={form.tax_id} onChange={set('tax_id')} /></FormField>
          <FormField label="Billing address" error={errors.billing_address} className="full"><textarea rows={2} value={form.billing_address} onChange={set('billing_address')} /></FormField>
          <FormField label="Shipping address" error={errors.shipping_address} className="full"><textarea rows={2} value={form.shipping_address} onChange={set('shipping_address')} /></FormField>
        </div>
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>{customer ? 'Save changes' : 'Create customer'}</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function CustomersPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const action = useAction();
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('company_name');
  const pg = usePagination({ status: '' });
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, error, loading, reload } = useAsync(
    () => listCustomers({ ...pg.params, q, sort: sort || 'company_name' }),
    [pg.page, pg.pageSize, pg.filters.status, q, sort],
  );
  const [editing, setEditing] = useState(null);
  const [deactivating, setDeactivating] = useState(null);
  const canWrite = can('customers:write');

  const columns = [
    { key: 'code', header: 'Code', sortable: true, render: (r) => <span className="mono">{r.code}</span> },
    { key: 'company_name', header: 'Company', sortable: true, render: (r) => <strong>{r.company_name}</strong> },
    { key: 'contact_person', header: 'Contact', render: (r) => r.contact_person || '—' },
    { key: 'email', header: 'Email', render: (r) => r.email || '—' },
    { key: 'phone', header: 'Phone', render: (r) => r.phone || '—' },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'created_at', header: 'Created', sortable: true, render: (r) => formatDate(r.created_at) },
    canWrite ? {
      key: 'actions', header: '', align: 'right', render: (r) => (
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <Button size="sm" variant="ghost" icon="edit" onClick={() => setEditing(r)}>Edit</Button>
          {r.status === 'ACTIVE' ? (
            <Button size="sm" variant="danger-outline" onClick={() => setDeactivating(r)}>Deactivate</Button>
          ) : (
            <Button size="sm" loading={action.isPending(`act-${r.id}`)} onClick={() => action.run(`act-${r.id}`, () => updateCustomer(r.id, { status: 'ACTIVE' }), { success: `${r.company_name} reactivated`, onSuccess: reload })}>Activate</Button>
          )}
        </div>
      ),
    } : null,
  ].filter(Boolean);

  return (
    <>
      <PageHeader
        title="Customers"
        subtitle="Accounts you sell to."
        actions={canWrite ? <Button variant="primary" icon="plus" onClick={() => setEditing({})}>New customer</Button> : null}
      />
      <FiltersBar>
        <SearchInput value={search} onChange={setSearch} placeholder="Search name, code, email…" />
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
        onRowClick={(r) => navigate(`/customers/${r.id}`)}
        emptyTitle="No customers match"
      />
      <CustomerFormModal
        open={editing !== null}
        customer={editing && editing.id ? editing : null}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); reload(); }}
      />
      <ConfirmDialog
        open={!!deactivating}
        title="Deactivate customer"
        message={deactivating ? `Deactivate ${deactivating.company_name}? Inactive customers cannot receive new orders.` : ''}
        confirmLabel="Deactivate"
        onClose={() => setDeactivating(null)}
        onConfirm={async () => {
          const res = await action.run('deactivate', () => updateCustomer(deactivating.id, { status: 'INACTIVE' }), {
            success: `${deactivating.company_name} deactivated`, toastError: false,
            onSuccess: () => { setDeactivating(null); reload(); },
          });
          return res;
        }}
      />
    </>
  );
}
