import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { listJobs } from '../api/production';
import { listStages } from '../api/catalog';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { DataTable, FilterSelect, FilterToggle, FiltersBar, PageHeader, SearchInput, StatusBadge } from '../components';
import { formatDate, formatNumber, humanize } from '../utils/format';
import { JOB_STATUSES } from '../utils/status';
import { ProductionTabs } from './ProductionBoardPage';

export default function ProductionJobsPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const pg = usePagination({ status: params.get('status') || '', stage: '', overdue: params.get('overdue') === 'true' });
  const [search, setSearch] = useState('');
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const f = pg.filters;
  const { data, error, loading, reload } = useAsync(
    () => listJobs({ ...pg.params, q, overdue: f.overdue ? true : undefined }),
    [pg.page, pg.pageSize, f.status, f.stage, f.overdue, q],
  );
  const stages = useAsync(() => listStages(), []);

  const columns = [
    { key: 'job_number', header: 'Job', sortable: true, render: (r) => <strong>{r.job_number}</strong> },
    { key: 'order', header: 'Order', render: (r) => r.order.order_number },
    { key: 'product', header: 'Product', render: (r) => <div><span className="mono">{r.product.sku}</span><div className="small muted">{r.product.name}</div></div> },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'stage', header: 'Stage', render: (r) => r.current_stage?.stage_name || '—' },
    { key: 'priority', header: 'Priority', render: (r) => <StatusBadge status={r.priority} /> },
    { key: 'qty', header: 'Produced / planned', align: 'right', render: (r) => `${formatNumber(r.produced_quantity)} / ${formatNumber(r.planned_quantity)}` },
    { key: 'approved_quantity', header: 'Approved', align: 'right', render: (r) => formatNumber(r.approved_quantity) },
    { key: 'target_date', header: 'Target', sortable: true, render: (r) => (
      <span className={r.is_overdue ? 'tone-text-red' : ''}>{formatDate(r.target_date)}{r.is_overdue ? ' · overdue' : ''}</span>
    ) },
  ];

  return (
    <>
      <PageHeader title="Production" subtitle="All production jobs." />
      <ProductionTabs />
      <FiltersBar onReset={() => { setSearch(''); pg.setFilters({ status: '', stage: '', overdue: false }); }}>
        <SearchInput value={search} onChange={setSearch} placeholder="Job, order or product…" />
        <FilterSelect label="Status" value={f.status} onChange={(v) => pg.setFilter('status', v)} options={JOB_STATUSES.map((s) => ({ value: s, label: humanize(s) }))} />
        <FilterSelect label="Stage (in progress)" value={f.stage} onChange={(v) => pg.setFilter('stage', v)} options={(stages.data || []).map((s) => ({ value: s.code, label: s.name }))} />
        <FilterToggle label="Overdue only" checked={f.overdue} onChange={(v) => pg.setFilter('overdue', v)} />
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
        onRowClick={(r) => navigate(`/production/jobs/${r.id}`)}
        rowClassName={(r) => (r.is_overdue ? 'row-warn' : '')}
        emptyTitle="No jobs match"
      />
    </>
  );
}
