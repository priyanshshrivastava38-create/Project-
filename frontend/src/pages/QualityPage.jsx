import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { listInspections } from '../api/quality';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { useAuth } from '../context/AuthContext';
import { Button, DataTable, FilterSelect, FiltersBar, KeyValue, PageHeader, SearchInput, StatusBadge } from '../components';
import InspectionFormModal from '../components/InspectionFormModal';
import { formatDateTime, formatNumber } from '../utils/format';

const OUTCOMES = [{ value: 'PASS', label: 'Pass' }, { value: 'FAIL', label: 'Fail' }];

function InspectionDetails({ row }) {
  return (
    <div className="grid-2">
      <div>
        <div className="field-label">Checklist</div>
        {row.checklist.length ? (
          <table className="table table-dense">
            <tbody>
              {row.checklist.map((c, i) => (
                <tr key={i}>
                  <td>{c.check}</td>
                  <td><StatusBadge status={c.passed ? 'PASS' : 'FAIL'} /></td>
                  <td className="muted small">{c.note || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="muted small">No checklist items.</p>}
      </div>
      <KeyValue items={[
        ['Defect description', row.defect_description],
        ['Corrective action', row.corrective_action],
        ['Comments', row.comments],
      ]} />
    </div>
  );
}

export default function QualityPage() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const jobId = params.get('job') || '';
  const pg = usePagination({ outcome: params.get('outcome') || '' });
  const [search, setSearch] = useState(params.get('q') || '');
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q, jobId]); // eslint-disable-line react-hooks/exhaustive-deps
  const f = pg.filters;
  const { data, error, loading, reload } = useAsync(
    () => listInspections({ ...pg.params, q, job_id: jobId || undefined }),
    [pg.page, pg.pageSize, f.outcome, q, jobId],
  );
  const [creating, setCreating] = useState(false);
  const [reinspecting, setReinspecting] = useState(null);
  const canWrite = can('quality:write');
  const canJobs = can('production:read');

  const clearJob = () => setParams((p) => { p.delete('job'); return p; }, { replace: true });

  const columns = [
    { key: 'inspection_number', header: 'Inspection', render: (r) => (
      <div><strong>{r.inspection_number}</strong>{r.parent_id ? <div className="small muted">Re-inspection</div> : null}</div>
    ) },
    { key: 'job', header: 'Job', render: (r) => (canJobs ? <Link to={`/production/jobs/${r.job.id}`}>{r.job.job_number}</Link> : r.job.job_number) },
    { key: 'order_number', header: 'Order', render: (r) => (r.order_number && can('orders:read') ? <Link to={`/orders/${r.job.order_id}`}>{r.order_number}</Link> : r.order_number || '—') },
    { key: 'batch_ref', header: 'Batch', render: (r) => (r.batch_ref ? <span className="mono">{r.batch_ref}</span> : '—') },
    { key: 'inspected_at', header: 'Inspected', render: (r) => (
      <div>{formatDateTime(r.inspected_at)}{r.inspector ? <div className="small muted">{r.inspector.full_name}</div> : null}</div>
    ) },
    { key: 'quantity_inspected', header: 'Inspected qty', align: 'right', render: (r) => formatNumber(r.quantity_inspected) },
    { key: 'approved_quantity', header: 'Approved', align: 'right', render: (r) => formatNumber(r.approved_quantity) },
    { key: 'defect_quantity', header: 'Defects', align: 'right', render: (r) => formatNumber(r.defect_quantity) },
    { key: 'outcome', header: 'Outcome', render: (r) => (
      <div><StatusBadge status={r.outcome} />{r.reinspected ? <div className="small muted">Reinspected</div> : null}</div>
    ) },
    ...(canWrite ? [{ key: 'actions', header: '', render: (r) => (r.outcome === 'FAIL' && !r.reinspected
      ? <Button size="sm" onClick={() => setReinspecting(r)}>Re-inspect</Button> : null) }] : []),
  ];

  return (
    <>
      <PageHeader
        title="Quality"
        subtitle="Inspection records. Passed units become approved finished goods; failed units are held for re-inspection."
        actions={canWrite ? <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>Record inspection</Button> : null}
      />
      <FiltersBar onReset={() => { setSearch(''); clearJob(); pg.setFilters({ outcome: '' }); }}>
        <SearchInput value={search} onChange={setSearch} placeholder="Inspection or job number…" />
        <FilterSelect label="Outcome" value={f.outcome} onChange={(v) => pg.setFilter('outcome', v)} options={OUTCOMES} />
        {jobId ? (
          <span className="chip">
            Job #{jobId}{' '}
            <button type="button" className="btn btn-ghost btn-sm" onClick={clearJob} aria-label="Clear job filter">×</button>
          </span>
        ) : null}
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
        renderExpanded={(r) => <InspectionDetails row={r} />}
        rowClassName={(r) => (r.outcome === 'FAIL' && !r.reinspected ? 'row-warn' : '')}
        emptyTitle="No inspections match"
        emptyMessage={canWrite ? 'Record an inspection for a job at the Quality inspection stage.' : undefined}
      />
      <InspectionFormModal open={creating} onClose={() => setCreating(false)} onSaved={() => { setCreating(false); reload(); }} />
      <InspectionFormModal open={!!reinspecting} mode="reinspect" parent={reinspecting} onClose={() => setReinspecting(null)}
        onSaved={() => { setReinspecting(null); reload(); }} />
    </>
  );
}
