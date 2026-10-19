import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { listAuditLogs } from '../api/reports';
import { listUsers } from '../api/users';
import { fetchAll } from '../api/catalog';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { useAuth } from '../context/AuthContext';
import {
  Button, DataTable, FilterSelect, FiltersBar, PageHeader,
} from '../components';
import { formatDateTime, humanize } from '../utils/format';

// Values written by backend services via audit.record(); `action` filters by prefix on the server.
const ENTITY_TYPES = ['customer', 'delivery', 'document', 'material', 'order', 'product', 'production_job', 'quality_inspection', 'reservation', 'supplier', 'user'];
const ACTIONS = [
  'auth', 'customer', 'delivery', 'document', 'inventory', 'material', 'order', 'product', 'production', 'quality', 'supplier', 'user',
].map((a) => ({ value: `${a}.`, label: `${humanize(a)} (all)` }));

/** Detail routes for entities that have one, with the permission required to open it. */
const ENTITY_ROUTES = {
  order: ['/orders', 'orders:read'],
  customer: ['/customers', 'customers:read'],
  production_job: ['/production/jobs', 'production:read'],
  document: ['/documents', 'documents:read'],
};

export default function AuditLogPage() {
  const { can } = useAuth();
  const [params] = useSearchParams();
  const pg = usePagination({
    action: params.get('action') || '',
    entity_type: params.get('entity_type') || '',
    user_id: params.get('user_id') || '',
  }, { pageSize: 50 });
  const [entityId, setEntityId] = useState(params.get('entity_id') || '');
  const entity_id = useDebounced(entityId);
  useEffect(() => { pg.setPage(1); }, [entity_id]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, error, loading, reload } = useAsync(
    () => listAuditLogs({ ...pg.params, entity_id: /^\d+$/.test(entity_id) ? entity_id : '' }),
    [pg.page, pg.pageSize, pg.filters.action, pg.filters.entity_type, pg.filters.user_id, entity_id],
  );
  const users = useAsync(() => fetchAll(listUsers), [], { enabled: can('users:manage') });
  const filtered = Object.values(pg.filters).some(Boolean) || entityId;

  const entityCell = (r) => {
    const label = <>{humanize(r.entity_type)}{r.entity_id ? <span className="mono"> #{r.entity_id}</span> : null}</>;
    const route = ENTITY_ROUTES[r.entity_type];
    return route && r.entity_id && can(route[1]) ? <Link to={`${route[0]}/${r.entity_id}`}>{label}</Link> : label;
  };

  const columns = [
    { key: 'created_at', header: 'When', width: 170, render: (r) => <span className="small">{formatDateTime(r.created_at)}</span> },
    { key: 'user', header: 'User', render: (r) => r.user?.full_name || <span className="muted">System</span> },
    { key: 'action', header: 'Action', render: (r) => <span className="mono small">{r.action}</span> },
    { key: 'entity', header: 'Entity', render: entityCell },
    { key: 'summary', header: 'Summary' },
  ];

  return (
    <>
      <PageHeader
        title="Audit log"
        subtitle="Append-only record of business actions, newest first."
        actions={<Button icon="refresh" onClick={reload}>Refresh</Button>}
      />
      <FiltersBar onReset={filtered ? () => { pg.resetFilters(); setEntityId(''); } : undefined}>
        <FilterSelect
          label="Action"
          value={pg.filters.action}
          onChange={(v) => pg.setFilter('action', v)}
          options={pg.filters.action && !ACTIONS.some((a) => a.value === pg.filters.action) ? [...ACTIONS, pg.filters.action] : ACTIONS}
        />
        <FilterSelect
          label="Entity"
          value={pg.filters.entity_type}
          onChange={(v) => pg.setFilter('entity_type', v)}
          options={ENTITY_TYPES.map((t) => ({ value: t, label: humanize(t) }))}
        />
        <label className="filter-select">
          <span className="filter-label">Entity ID</span>
          <input type="number" min={1} value={entityId} onChange={(e) => setEntityId(e.target.value)} style={{ width: 90 }} />
        </label>
        {can('users:manage') ? (
          <FilterSelect
            label="User"
            value={pg.filters.user_id}
            onChange={(v) => pg.setFilter('user_id', v)}
            options={(users.data || []).map((u) => ({ value: String(u.id), label: u.full_name }))}
          />
        ) : null}
      </FiltersBar>
      <DataTable
        columns={columns}
        rows={data?.items}
        loading={loading}
        error={error}
        onRetry={reload}
        dense
        page={pg.page}
        pageSize={pg.pageSize}
        total={data?.total}
        onPageChange={pg.setPage}
        onPageSizeChange={pg.setPageSize}
        emptyTitle={filtered ? 'No entries match these filters' : 'No audit entries yet'}
        renderExpanded={(r) => (r.details && Object.keys(r.details).length
          ? <pre className="json">{JSON.stringify(r.details, null, 2)}</pre>
          : <span className="muted small">No additional details recorded.</span>)}
      />
    </>
  );
}
