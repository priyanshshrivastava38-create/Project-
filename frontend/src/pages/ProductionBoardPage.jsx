import { useNavigate } from 'react-router-dom';
import { getBoard } from '../api/production';
import { useAsync } from '../hooks/useAsync';
import { Button, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge, Tabs } from '../components';
import { formatDate, formatNumber } from '../utils/format';

export function ProductionTabs() {
  return <Tabs tabs={[{ value: 'board', label: 'Board', to: '/production' }, { value: 'list', label: 'Job list', to: '/production/jobs' }]} />;
}

function JobCard({ job, onOpen }) {
  return (
    <button type="button" className={`job-card ${job.is_overdue ? 'overdue' : ''}`} onClick={onOpen}
      aria-label={`${job.job_number}, ${job.product.sku}${job.is_overdue ? ', overdue' : ''}`}>
      <div className="job-card-top">
        <span className="job-number">{job.job_number}</span>
        <StatusBadge status={job.priority} />
      </div>
      <div className="job-product"><span className="mono">{job.product.sku}</span> · {job.product.name}</div>
      <div className="row-between small">
        <span className="muted">{job.order.order_number}</span>
        <span><strong>{formatNumber(job.produced_quantity)}</strong> / {formatNumber(job.planned_quantity)} {job.product.uom}</span>
      </div>
      <div className="row-between small">
        <span className="muted">Target {formatDate(job.target_date)}</span>
        {job.is_overdue ? <StatusBadge status="OVERDUE" label="Overdue" tone="red" /> : null}
      </div>
    </button>
  );
}

export default function ProductionBoardPage() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsync(() => getBoard(), []);
  const total = (data || []).reduce((n, c) => n + c.jobs.length, 0);

  return (
    <>
      <PageHeader
        title="Production"
        subtitle="Jobs by current stage. Click a card to open the job."
        actions={<Button icon="refresh" onClick={reload} loading={loading && !!data}>Refresh</Button>}
      />
      <ProductionTabs />
      {error ? <ErrorState error={error} onRetry={reload} /> : !data ? <Spinner /> : total === 0 ? (
        <EmptyState title="No production jobs" message="Jobs are created from confirmed sales order lines." icon="production" />
      ) : (
        <div className="board" role="list" aria-label="Production board">
          {data.map((col) => (
            <section key={col.key} className="board-col" role="listitem" aria-label={col.title}>
              <div className="board-col-head"><span>{col.title}</span><span className="board-count">{col.jobs.length}</span></div>
              {col.jobs.map((j) => <JobCard key={j.id} job={j} onOpen={() => navigate(`/production/jobs/${j.id}`)} />)}
              {!col.jobs.length ? <span className="muted small" style={{ padding: 4 }}>No jobs</span> : null}
            </section>
          ))}
        </div>
      )}
    </>
  );
}
