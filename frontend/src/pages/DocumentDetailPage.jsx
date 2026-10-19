import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { approveDocument, archiveDocument, downloadDocument, getDocument, listApprovals } from '../api/documents';
import { useAsync } from '../hooks/useAsync';
import { useAction } from '../hooks/useAction';
import { useAuth } from '../context/AuthContext';
import {
  Alert, Button, Card, ConfirmDialog, ErrorState, FormField, KeyValue, PageHeader, Spinner, StatusBadge, Timeline,
} from '../components';
import { UploadDocumentModal } from './DocumentsPage';
import { formatBytes, formatDateTime, humanize } from '../utils/format';
import { statusTone } from '../utils/status';

export default function DocumentDetailPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const action = useAction();
  const { data: doc, error, reload } = useAsync(() => getDocument(id), [id]);
  const approvals = useAsync(() => listApprovals(id), [id]);
  const [dialog, setDialog] = useState(null); // {kind: 'approve', version} | {kind: 'archive'}
  const [comment, setComment] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);

  if (error && !doc) return <ErrorState error={error} onRetry={reload} />;
  if (!doc) return <Spinner />;

  const canApprove = can('documents:approve');
  const canManage = canApprove || can('documents:upload');
  const versions = [...doc.versions].reverse();
  const current = versions.find((v) => v.status === 'APPROVED');
  const latestDraft = versions.find((v) => v.status === 'DRAFT');
  const versionNo = Object.fromEntries(doc.versions.map((v) => [v.id, v.version_number]));
  const refresh = () => { reload(); approvals.reload(); };
  const open = (d) => { setComment(''); setDialog(d); };

  const headerVersion = current || versions[0];
  const download = (v) => action.run(`dl-${v?.id}`, () => downloadDocument(doc.id, v?.id, v?.source_filename || doc.title));

  const timeline = [...(approvals.data || [])].reverse().map((a) => ({
    status: a.action,
    note: [`v${versionNo[a.version_id] ?? '?'}`, a.comment].filter(Boolean).join(' · '),
    by: a.user?.full_name,
    at: a.created_at,
    tone: statusTone(a.action),
  }));

  return (
    <>
      <PageHeader
        title={doc.title}
        meta={<StatusBadge status={doc.status} />}
        subtitle={humanize(doc.doc_type)}
        breadcrumbs={[{ label: 'Documents', to: '/documents' }, { label: doc.title }]}
        actions={(
          <>
            {current || canManage ? (
              <Button icon="download" loading={action.isPending(`dl-${headerVersion?.id}`)} disabled={action.anyPending} onClick={() => download(headerVersion)}>
                Download
              </Button>
            ) : null}
            {can('documents:upload') ? <Button icon="upload" onClick={() => setUploadOpen(true)}>Upload new version</Button> : null}
            {canApprove && latestDraft ? (
              <Button variant="primary" icon="check" onClick={() => open({ kind: 'approve', version: latestDraft })}>
                Approve v{latestDraft.version_number}
              </Button>
            ) : null}
            {canApprove && doc.status !== 'ARCHIVED' ? (
              <Button variant="danger-outline" onClick={() => open({ kind: 'archive' })}>Archive</Button>
            ) : null}
          </>
        )}
      />

      {doc.status === 'ARCHIVED' ? <Alert tone="info">This document is archived and is not used by the assistant.</Alert> : null}

      <div className="grid-2 section-gap">
        <Card title="Details">
          <KeyValue items={[
            ['Type', humanize(doc.doc_type)],
            ['Status', <StatusBadge key="s" status={doc.status} />],
            ['Current version', current ? `v${current.version_number} (approved ${formatDateTime(current.approved_at)})` : 'None approved'],
            ['Visible to', doc.allowed_roles.length ? doc.allowed_roles.map(humanize).join(', ') : 'All roles'],
            ['Created', formatDateTime(doc.created_at)],
            ['Updated', formatDateTime(doc.updated_at)],
          ]} />
        </Card>
        <Card title="Approval history">
          {approvals.error ? <ErrorState error={approvals.error} onRetry={approvals.reload} title="Could not load approvals" />
            : approvals.loading && !approvals.data ? <Spinner /> : <Timeline entries={timeline} />}
        </Card>
      </div>

      <Card title="Versions" padded={false}>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Version</th><th>Status</th><th>File</th><th className="num">Size</th><th className="num">Pages</th>
                <th>Uploaded</th><th>Approved</th><th />
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.id}>
                  <td>v{v.version_number}</td>
                  <td><StatusBadge status={v.status} /></td>
                  <td>
                    <span className="mono small">{v.source_filename}</span>
                    {v.extraction_note ? <div className="small tone-text-amber">{v.extraction_note}</div> : null}
                  </td>
                  <td className="num">{formatBytes(v.size_bytes)}</td>
                  <td className="num">{v.page_count ?? '—'}</td>
                  <td>{formatDateTime(v.uploaded_at)}<div className="small muted">{v.uploaded_by?.full_name}</div></td>
                  <td>{v.approved_at ? <>{formatDateTime(v.approved_at)}<div className="small muted">{v.approved_by?.full_name}</div></> : '—'}</td>
                  <td>
                    <div className="row" style={{ justifyContent: 'flex-end' }}>
                      {v.status === 'APPROVED' || canManage ? (
                        <Button size="sm" variant="ghost" icon="download" loading={action.isPending(`dl-${v.id}`)} disabled={action.anyPending} onClick={() => download(v)}>
                          Download
                        </Button>
                      ) : null}
                      {canApprove && v.status === 'DRAFT' ? (
                        <Button size="sm" onClick={() => open({ kind: 'approve', version: v })}>Approve</Button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <ConfirmDialog
        open={dialog?.kind === 'approve'}
        title={dialog?.version ? `Approve v${dialog.version.version_number}` : 'Approve'}
        message={current ? `The currently approved v${current.version_number} will be archived.` : 'This version becomes the authoritative one used by the assistant.'}
        confirmLabel="Approve"
        tone="primary"
        onClose={() => setDialog(null)}
        onConfirm={() => action.run('approve', () => approveDocument(doc.id, { version_id: dialog.version.id, comment: comment.trim() || null }), {
          success: `v${dialog.version.version_number} approved`, toastError: false, onSuccess: () => { setDialog(null); refresh(); },
        })}
      >
        <FormField label="Comment" hint="Optional">
          <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} />
        </FormField>
      </ConfirmDialog>
      <ConfirmDialog
        open={dialog?.kind === 'archive'}
        title={`Archive ${doc.title}`}
        message="All versions will be archived and the document will no longer be used by the assistant. Uploading a new version later makes it a draft again."
        confirmLabel="Archive"
        onClose={() => setDialog(null)}
        onConfirm={() => action.run('archive', () => archiveDocument(doc.id, { comment: comment.trim() || null }), {
          success: `${doc.title} archived`, toastError: false, onSuccess: () => { setDialog(null); refresh(); },
        })}
      >
        <FormField label="Comment" hint="Optional">
          <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} />
        </FormField>
      </ConfirmDialog>
      <UploadDocumentModal
        open={uploadOpen}
        document={doc}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => { setUploadOpen(false); refresh(); }}
      />
    </>
  );
}
