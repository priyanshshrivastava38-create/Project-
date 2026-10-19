import { useEffect, useState } from 'react';
import { createUser, listUsers, updateUser } from '../api/users';
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
import { formatDateTime, humanize } from '../utils/format';
import { ROLES } from '../utils/status';

const ROLE_OPTIONS = ROLES.map((r) => ({ value: r, label: humanize(r) }));
const MIN_PASSWORD = 10;
const EMPTY = { email: '', full_name: '', role: '', is_active: true, password: '', confirm: '' };

function validate(form, isNew) {
  const e = {};
  if (isNew && !/^\S+@\S+\.\S+$/.test(form.email.trim())) e.email = 'Enter a valid email address';
  if (form.full_name.trim().length < 2) e.full_name = 'Name must be at least 2 characters';
  if (!form.role) e.role = 'Select a role';
  if (isNew || form.password) {
    if (form.password.length < MIN_PASSWORD) e.password = `Password must be at least ${MIN_PASSWORD} characters`;
    else if (form.password !== form.confirm) e.confirm = 'Passwords do not match';
  }
  return e;
}

function UserFormModal({ open, user, isSelf, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);
  const isNew = !user;

  useEffect(() => {
    if (open) {
      setForm(user ? { ...EMPTY, email: user.email, full_name: user.full_name, role: user.role, is_active: user.is_active } : EMPTY);
      setErrors({}); setFormError('');
    }
  }, [open, user]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    const v = validate(form, isNew);
    setErrors(v); setFormError('');
    if (Object.keys(v).length) return;
    let body;
    if (isNew) {
      body = { email: form.email.trim(), full_name: form.full_name.trim(), role: form.role, password: form.password };
    } else {
      // PATCH only what changed so the audit trail stays meaningful.
      body = {};
      if (form.full_name.trim() !== user.full_name) body.full_name = form.full_name.trim();
      if (form.role !== user.role) body.role = form.role;
      if (form.is_active !== user.is_active) body.is_active = form.is_active;
      if (form.password) body.password = form.password;
      if (!Object.keys(body).length) { onClose(); return; }
    }
    setPending(true);
    try {
      const saved = isNew ? await createUser(body) : await updateUser(user.id, body);
      toast.success(isNew ? `User ${saved.email} created` : `User ${saved.email} updated${body.password ? ' — password reset and sessions signed out' : ''}`);
      onSaved(saved);
    } catch (err) {
      const fe = fieldErrors(err);
      setErrors(fe);
      setFormError(Object.keys(fe).length ? err.message : errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  const privilegeChange = !isNew && (form.role !== user.role || (user.is_active && !form.is_active));

  return (
    <Modal open={open} title={isNew ? 'New user' : `Edit ${user.full_name}`} onClose={onClose} busy={pending}>
      <form onSubmit={submit} className="stack" noValidate>
        <div className="form-grid">
          <FormField label="Email" required={isNew} error={errors.email} className="full" hint={isNew ? undefined : 'Email cannot be changed'}>
            <input type="email" value={form.email} onChange={set('email')} disabled={!isNew} autoComplete="off" maxLength={255} />
          </FormField>
          <FormField label="Full name" required error={errors.full_name}>
            <input value={form.full_name} onChange={set('full_name')} maxLength={120} />
          </FormField>
          <FormField label="Role" required error={errors.role} hint={isSelf ? 'You cannot change your own role' : undefined}>
            <select value={form.role} onChange={set('role')} disabled={isSelf}>
              <option value="" disabled>Select a role…</option>
              {ROLE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </FormField>
          {!isNew ? (
            <div className="field full">
              <label className="checkbox">
                <input type="checkbox" checked={form.is_active} onChange={set('is_active')} disabled={isSelf} />
                <span>Active {isSelf ? <span className="muted small">(you cannot deactivate your own account)</span> : null}</span>
              </label>
              {errors.is_active ? <div className="field-err">{errors.is_active}</div> : null}
            </div>
          ) : null}
          <FormField
            label={isNew ? 'Password' : 'New password'}
            required={isNew}
            error={errors.password}
            hint={isNew ? `At least ${MIN_PASSWORD} characters` : `Leave blank to keep the current password (min ${MIN_PASSWORD} characters)`}
          >
            <input type="password" value={form.password} onChange={set('password')} autoComplete="new-password" maxLength={128} />
          </FormField>
          <FormField label="Confirm password" required={isNew} error={errors.confirm}>
            <input type="password" value={form.confirm} onChange={set('confirm')} autoComplete="new-password" maxLength={128} disabled={!isNew && !form.password} />
          </FormField>
        </div>
        {privilegeChange || (!isNew && form.password) ? (
          <Alert tone="info">Saving will sign this user out of all active sessions.</Alert>
        ) : null}
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending}>{isNew ? 'Create user' : 'Save changes'}</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function UsersPage() {
  const { user: me, reloadUser } = useAuth();
  const action = useAction();
  const [search, setSearch] = useState('');
  const pg = usePagination({ role: '' });
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, error, loading, reload } = useAsync(
    () => listUsers({ ...pg.params, q }),
    [pg.page, pg.pageSize, pg.filters.role, q],
  );
  const [editing, setEditing] = useState(null);
  const [deactivating, setDeactivating] = useState(null);

  const columns = [
    { key: 'full_name', header: 'Name', render: (r) => (
      <div>
        <strong>{r.full_name}</strong>
        {r.id === me?.id ? <span className="chip" style={{ marginLeft: 6 }}>You</span> : null}
        <div className="small muted">{r.email}</div>
      </div>
    ) },
    { key: 'role', header: 'Role', render: (r) => humanize(r.role) },
    { key: 'is_active', header: 'Status', render: (r) => <StatusBadge status={r.is_active ? 'ACTIVE' : 'INACTIVE'} /> },
    { key: 'last_login_at', header: 'Last login', render: (r) => formatDateTime(r.last_login_at, 'Never') },
    { key: 'created_at', header: 'Created', render: (r) => formatDateTime(r.created_at) },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <Button size="sm" variant="ghost" icon="edit" onClick={() => setEditing(r)}>Edit</Button>
        {r.id === me?.id ? null : r.is_active
          ? <Button size="sm" variant="danger-outline" onClick={() => setDeactivating(r)}>Deactivate</Button>
          : <Button size="sm" loading={action.isPending(`a-${r.id}`)} onClick={() => action.run(`a-${r.id}`, () => updateUser(r.id, { is_active: true }), { success: `${r.full_name} reactivated`, onSuccess: reload })}>Activate</Button>}
      </div>
    ) },
  ];

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Accounts, roles and access."
        actions={<Button variant="primary" icon="plus" onClick={() => setEditing({})}>New user</Button>}
      />
      <FiltersBar onReset={search || pg.filters.role ? () => { setSearch(''); pg.resetFilters(); } : undefined}>
        <SearchInput value={search} onChange={setSearch} placeholder="Search name or email…" />
        <FilterSelect label="Role" value={pg.filters.role} onChange={(v) => pg.setFilter('role', v)} options={ROLE_OPTIONS} />
      </FiltersBar>
      <DataTable
        columns={columns}
        rows={data?.items}
        loading={loading}
        error={error}
        onRetry={reload}
        rowClassName={(r) => (r.is_active ? '' : 'muted')}
        page={pg.page}
        pageSize={pg.pageSize}
        total={data?.total}
        onPageChange={pg.setPage}
        onPageSizeChange={pg.setPageSize}
        emptyTitle="No users match"
      />
      <UserFormModal
        open={editing !== null}
        user={editing && editing.id ? editing : null}
        isSelf={!!editing && editing.id === me?.id}
        onClose={() => setEditing(null)}
        onSaved={(saved) => { setEditing(null); reload(); if (saved.id === me?.id) reloadUser(); }}
      />
      <ConfirmDialog
        open={!!deactivating}
        title="Deactivate user"
        message={deactivating ? `Deactivate ${deactivating.full_name} (${deactivating.email})? They will be signed out and unable to log in.` : ''}
        confirmLabel="Deactivate"
        onClose={() => setDeactivating(null)}
        onConfirm={() => action.run('deact', () => updateUser(deactivating.id, { is_active: false }), {
          success: `${deactivating.full_name} deactivated`, toastError: false,
          onSuccess: () => { setDeactivating(null); reload(); },
        })}
      />
    </>
  );
}
