import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listDocuments, uploadDocument } from '../api/documents';
import { errorMessage, fieldErrors } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useDebounced } from '../hooks/useDebounced';
import { useAuth } from '../context/AuthContext';
import {
  Alert, Button, DataTable, FilterSelect, FiltersBar, FormField, Modal, PageHeader, SearchInput, StatusBadge, useToast,
} from '../components';
import { formatDateTime, humanize } from '../utils/format';
import { DOC_STATUSES, DOC_TYPES, ROLES } from '../utils/status';

const ACCEPT = '.pdf,.txt,.md,.markdown,.docx';
const EMPTY = { file: null, title: '', doc_type: 'OTHER', allowed_roles: [] };

/** Upload a new document, or a new version of `document` when given. */
export function UploadDocumentModal({ open, document, onClose, onUploaded }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) { setForm(EMPTY); setErrors({}); setFormError(''); }
  }, [open]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const toggleRole = (r) => setForm((f) => ({
    ...f, allowed_roles: f.allowed_roles.includes(r) ? f.allowed_roles.filter((x) => x !== r) : [...f.allowed_roles, r],
  }));

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.file) errs.file = 'Choose a file to upload';
    if (!document && form.title.trim().length < 3) errs.title = 'Title must be at least 3 characters';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const fd = new FormData();
    fd.append('file', form.file);
    if (document) {
      fd.append('document_id', String(document.id));
    } else {
      fd.append('title', form.title.trim());
      fd.append('doc_type', form.doc_type);
      fd.append('allowed_roles', JSON.stringify(form.allowed_roles));
    }
    setPending(true); setFormError('');
    try {
      const saved = await uploadDocument(fd);
      toast.success(document ? `New version of "${saved.title}" uploaded as draft` : `"${saved.title}" uploaded as draft`);
      onUploaded(saved);
    } catch (err) {
      const fe = fieldErrors(err);
      setErrors(fe);
      setFormError(Object.keys(fe).length ? err.message : errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title={document ? `Upload new version of ${document.title}` : 'Upload document'} onClose={onClose} busy={pending} size="lg">
      <form onSubmit={submit} className="stack" noValidate>
        <div className="form-grid">
          <FormField label="File" required error={errors.file} hint="PDF, TXT, Markdown or DOCX, max 10 MB" className="full">
            <input type="file" accept={ACCEPT} onChange={(e) => setForm((f) => ({ ...f, file: e.target.files?.[0] || null }))} />
          </FormField>
          {!document ? (
            <>
              <FormField label="Title" required error={errors.title}>
                <input value={form.title} onChange={set('title')} maxLength={200} />
              </FormField>
              <FormField label="Type" error={errors.doc_type}>
                <select value={form.doc_type} onChange={set('doc_type')}>
                  {DOC_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
                </select>
              </FormField>
            </>
          ) : null}
        </div>
        {!document ? (
          <fieldset className="card" style={{ padding: 12 }}>
            <legend className="field-label" style={{ padding: '0 4px' }}>Visible to roles</legend>
            <p className="muted small" style={{ marginTop: 0 }}>Leave all unchecked to make the document visible to every role.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 6 }}>
              {ROLES.map((r) => (
                <label key={r} className="checkbox">
                  <input type="checkbox" checked={form.allowed_roles.includes(r)} onChange={() => toggleRole(r)} />
                  <span>{humanize(r)}</span>
                </label>
              ))}
            </div>
            {errors.allowed_roles ? <div className="field-err">{errors.allowed_roles}</div> : null}
          </fieldset>
        ) : <p className="muted small">The new version is stored as a draft until it is approved.</p>}
        {formError ? <Alert>{formError}</Alert> : null}
        <div className="modal-actions">
          <Button onClick={onClose} disabled={pending}>Cancel</Button>
          <Button type="submit" variant="primary" icon="upload" loading={pending}>Upload</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function DocumentsPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [docType, setDocType] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const q = useDebounced(search);
  const { data, error, loading, reload } = useAsync(
    () => listDocuments({ q, status, doc_type: docType }),
    [q, status, docType],
  );

  const latest = (d) => d.versions[d.versions.length - 1];
  const columns = [
    { key: 'title', header: 'Title', sortable: true, render: (r) => <strong>{r.title}</strong> },
    { key: 'doc_type', header: 'Type', sortable: true, render: (r) => humanize(r.doc_type) },
    { key: 'status', header: 'Status', sortable: true, render: (r) => <StatusBadge status={r.status} /> },
    { key: 'version', header: 'Latest version', sortValue: (r) => latest(r)?.version_number, sortable: true, render: (r) => {
      const v = latest(r);
      return v ? <span>v{v.version_number} <span className="muted small">{v.source_filename}</span></span> : '—';
    } },
    { key: 'allowed_roles', header: 'Visible to', render: (r) => (
      r.allowed_roles?.length
        ? <div className="chip-list">{r.allowed_roles.map((x) => <span key={x} className="chip">{humanize(x)}</span>)}</div>
        : <span className="muted">All roles</span>
    ) },
    { key: 'updated_at', header: 'Updated', sortable: true, render: (r) => formatDateTime(r.updated_at) },
  ];

  return (
    <>
      <PageHeader
        title="Documents"
        subtitle="Procedures, specifications and policies. Only approved versions are used by the assistant."
        actions={can('documents:upload') ? <Button variant="primary" icon="upload" onClick={() => setUploadOpen(true)}>Upload document</Button> : null}
      />
      <FiltersBar onReset={search || status || docType ? () => { setSearch(''); setStatus(''); setDocType(''); } : undefined}>
        <SearchInput value={search} onChange={setSearch} placeholder="Search title or type…" />
        <FilterSelect label="Status" value={status} onChange={setStatus} options={DOC_STATUSES.map((s) => ({ value: s, label: humanize(s) }))} />
        <FilterSelect label="Type" value={docType} onChange={setDocType} options={DOC_TYPES.map((t) => ({ value: t, label: humanize(t) }))} />
      </FiltersBar>
      <DataTable
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        onRetry={reload}
        onRowClick={(r) => navigate(`/documents/${r.id}`)}
        emptyTitle="No documents match"
        emptyMessage={can('documents:upload') ? 'Upload a document to get started.' : undefined}
      />
      <UploadDocumentModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={(doc) => { setUploadOpen(false); navigate(`/documents/${doc.id}`); }}
      />
    </>
  );
}
