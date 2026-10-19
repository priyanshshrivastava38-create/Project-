import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { getInventoryAlerts, getProductionTrend, getSummary } from '../api/dashboard';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../context/AuthContext';
import {
  Button, Card, EmptyState, ErrorState, FilterDate, FiltersBar, Icon, KpiCard, PageHeader, Spinner,
} from '../components';
import { formatDateTime, formatMoney, formatNumber, humanize, toNumber } from '../utils/format';
import { STATUS_CHART_COLORS, activityIcon, friendlyText } from '../utils/status';

export default function DashboardPage() {
  const { can } = useAuth();
  const [range, setRange] = useState({ date_from: '', date_to: '' });
  const [days, setDays] = useState(30);
  const summary = useAsync(() => getSummary(range), [range.date_from, range.date_to]);
  const trend = useAsync(() => getProductionTrend(days), [days]);
  const alerts = useAsync(() => getInventoryAlerts(), []);
  const s = summary.data;

  const kpis = s ? [
    { label: 'Total orders', value: formatNumber(s.total_orders), to: '/orders' },
    { label: 'Booked order value', value: formatMoney(s.booked_order_value) },
    { label: 'Awaiting production', value: formatNumber(s.orders_awaiting_production), to: '/orders?status=CONFIRMED' },
    { label: 'Active production jobs', value: formatNumber(s.active_production_jobs), to: '/production' },
    { label: 'Overdue jobs', value: formatNumber(s.overdue_jobs), tone: s.overdue_jobs > 0 ? 'red' : undefined, to: '/production/jobs?overdue=true' },
    { label: 'Pending QC inspections', value: formatNumber(s.pending_quality_inspections), tone: s.pending_quality_inspections > 0 ? 'amber' : undefined, to: '/quality' },
    { label: 'Low-stock alerts', value: formatNumber(s.low_stock_alerts), tone: s.low_stock_alerts > 0 ? 'amber' : undefined, to: '/inventory?low_stock=true' },
    { label: 'Ready for dispatch', value: formatNumber(s.orders_ready_for_dispatch), to: '/deliveries' },
    { label: 'Deliveries in transit', value: formatNumber(s.deliveries_in_transit), to: '/deliveries?status=IN_TRANSIT' },
  ].map((k) => {
    // Only link to pages the user can open.
    const perm = { '/orders': 'orders:read', '/production': 'production:read', '/quality': 'quality:read', '/inventory': 'inventory:read', '/deliveries': 'deliveries:read' };
    const base = k.to ? `/${k.to.split('/')[1].split('?')[0]}` : null;
    return base && !can(perm[base]) ? { ...k, to: undefined } : k;
  }) : [];

  const trendData = (trend.data?.series || []).map((p) => ({
    date: p.date.slice(5),
    jobs_completed: p.jobs_completed,
    on_time: p.on_time,
    units_approved: toNumber(p.units_approved) || 0,
  }));
  const distribution = (s?.order_status_distribution || []).map((d) => ({ ...d, label: humanize(d.status) }));
  const hasDistribution = distribution.some((d) => d.count > 0);

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Live operational overview across sales, production, quality and dispatch."
        actions={<Button icon="refresh" onClick={() => { summary.reload(); trend.reload(); alerts.reload(); }}>Refresh</Button>}
      />
      <FiltersBar onReset={range.date_from || range.date_to ? () => setRange({ date_from: '', date_to: '' }) : undefined}>
        <FilterDate label="Orders from" value={range.date_from} onChange={(v) => setRange((r) => ({ ...r, date_from: v }))} />
        <FilterDate label="Orders to" value={range.date_to} onChange={(v) => setRange((r) => ({ ...r, date_to: v }))} />
      </FiltersBar>

      {summary.error ? <ErrorState error={summary.error} onRetry={summary.reload} /> : null}
      {summary.loading && !s ? <Spinner /> : null}
      {s ? <div className="kpi-grid">{kpis.map((k) => <KpiCard key={k.label} {...k} />)}</div> : null}

      <div className="dash-grid">
        <div className="col-5">
          <Card title="Orders by status">
            {!s ? (summary.loading ? <Spinner /> : null) : !hasDistribution ? (
              <EmptyState title="No orders in this range" />
            ) : (
              <div className="chart-box">
                <ResponsiveContainer>
                  <BarChart data={distribution} layout="vertical" margin={{ left: 24, right: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
                    <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="count" name="Orders" radius={[0, 4, 4, 0]}>
                      {distribution.map((d) => <Cell key={d.status} fill={STATUS_CHART_COLORS[d.status] || '#64748b'} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </div>
        <div className="col-7">
          <Card
            title="Production trend"
            subtitle="Jobs completed and QC-approved units per day"
            actions={(
              <label className="filter-select">
                <span className="sr-only">Days</span>
                <select className="inline-control" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                  {[7, 14, 30, 60, 90, 180].map((d) => <option key={d} value={d}>Last {d} days</option>)}
                </select>
              </label>
            )}
          >
            {trend.error ? <ErrorState error={trend.error} onRetry={trend.reload} /> : trend.loading && !trend.data ? <Spinner /> : !trendData.length ? (
              <EmptyState title="No production data" />
            ) : (
              <div className="chart-box">
                <ResponsiveContainer>
                  <ComposedChart data={trendData} margin={{ right: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={16} />
                    <YAxis yAxisId="left" allowDecimals={false} tick={{ fontSize: 11 }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar yAxisId="right" dataKey="units_approved" name="Units approved" fill="#93b4ef" radius={[3, 3, 0, 0]} />
                    <Line yAxisId="left" type="monotone" dataKey="jobs_completed" name="Jobs completed" stroke="#2557c7" strokeWidth={2} dot={false} />
                    <Line yAxisId="left" type="monotone" dataKey="on_time" name="On time" stroke="#16a34a" strokeWidth={2} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </div>
        <div className="col-6">
          <Card title="Low-stock materials" actions={can('inventory:read') ? <Link to="/inventory?low_stock=true">View inventory</Link> : null}>
            {alerts.error ? <ErrorState error={alerts.error} onRetry={alerts.reload} /> : alerts.loading && !alerts.data ? <Spinner /> : !alerts.data?.length ? (
              <EmptyState title="All materials above reorder level" icon="check" />
            ) : (
              <div className="table-scroll">
                <table className="table table-dense">
                  <thead><tr><th>Material</th><th className="num">Available</th><th className="num">Reorder level</th><th className="num">Shortfall</th><th>Supplier</th></tr></thead>
                  <tbody>
                    {alerts.data.map((a) => (
                      <tr key={a.material_id} className="row-warn">
                        <td><div className="mono">{a.sku}</div><div className="small muted">{a.name}</div></td>
                        <td className="num">{formatNumber(a.available)} {a.uom}</td>
                        <td className="num">{formatNumber(a.reorder_level)}</td>
                        <td className="num tone-text-red">{formatNumber(a.shortfall)}</td>
                        <td>{a.preferred_supplier || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
        <div className="col-6">
          <Card title="Recent activity">
            {!s ? (summary.loading ? <Spinner /> : null) : !s.recent_activity?.length ? <EmptyState title="No recent activity" /> : (
              <ul className="activity-list">
                {s.recent_activity.slice(0, 10).map((a) => (
                  <li key={a.id}>
                    <span className="activity-icon" aria-hidden="true"><Icon name={activityIcon(a.action)} size={14} /></span>
                    <div style={{ flex: 1 }}>
                      <div>{friendlyText(a.summary)}</div>
                      <div className="small muted">{a.user || 'System'} · {formatDateTime(a.created_at)}</div>
                    </div>
                    <span className="activity-action">{humanize(a.action.split('.').slice(1).join(' ')) || humanize(a.action)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
