import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { fulfillmentReport, ordersByCustomer, productionPerformance, qualityReport } from '../api/reports';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../context/AuthContext';
import {
  Button, Card, DataTable, EmptyState, ErrorState, FilterDate, FiltersBar, KpiCard, PageHeader, ProgressBar, Spinner,
  StatusBadge,
} from '../components';
import {
  formatDate, formatDateTime, formatMoney, formatNumber, formatPercent, toNumber,
} from '../utils/format';

/** Loading / error / content switch shared by every report section. */
function Section({ state, children }) {
  if (state.error) return <ErrorState error={state.error} onRetry={state.reload} />;
  if (state.loading && !state.data) return <Spinner />;
  return state.data ? children(state.data) : null;
}

const pctTone = (v, good, warn) => {
  const n = toNumber(v);
  if (n === null) return undefined;
  return n >= good ? 'green' : n >= warn ? 'amber' : 'red';
};

export default function ReportsPage() {
  const { can } = useAuth();
  const [range, setRange] = useState({ date_from: '', date_to: '' });
  const customers = useAsync(() => ordersByCustomer(range), [range.date_from, range.date_to]);
  const production = useAsync(() => productionPerformance(), []);
  const quality = useAsync(() => qualityReport(), []);
  const fulfillment = useAsync(() => fulfillmentReport(), []);
  const reloadAll = () => { customers.reload(); production.reload(); quality.reload(); fulfillment.reload(); };
  const rangeInvalid = range.date_from && range.date_to && range.date_from > range.date_to;

  const customerColumns = [
    { key: 'customer', header: 'Customer', sortable: true, render: (r) => (
      can('customers:read') ? <Link to={`/customers/${r.customer_id}`}>{r.customer}</Link> : r.customer
    ) },
    { key: 'orders', header: 'Orders', sortable: true, align: 'right', render: (r) => formatNumber(r.orders) },
    { key: 'total_value', header: 'Order value', sortable: true, align: 'right', render: (r) => formatMoney(r.total_value) },
  ];

  const jobColumns = [
    { key: 'job_number', header: 'Job', sortable: true, render: (r) => <span className="mono">{r.job_number}</span> },
    { key: 'product', header: 'Product', sortable: true, render: (r) => <span className="mono">{r.product}</span> },
    { key: 'planned', header: 'Planned', align: 'right', sortable: true, render: (r) => formatNumber(r.planned) },
    { key: 'approved', header: 'Approved', align: 'right', sortable: true, render: (r) => formatNumber(r.approved) },
    { key: 'rejected', header: 'Rejected', align: 'right', sortable: true, render: (r) => (
      <span className={toNumber(r.rejected) > 0 ? 'tone-text-red' : ''}>{formatNumber(r.rejected)}</span>
    ) },
    { key: 'target_date', header: 'Target', sortable: true, render: (r) => formatDate(r.target_date) },
    { key: 'completed', header: 'Completed', sortable: true, render: (r) => formatDateTime(r.completed) },
    { key: 'on_time', header: 'On time', sortable: true, sortValue: (r) => (r.on_time ? 1 : 0), render: (r) => (
      <StatusBadge status={r.on_time ? 'ON_TIME' : 'LATE'} label={r.on_time ? 'On time' : 'Late'} tone={r.on_time ? 'green' : 'red'} />
    ) },
  ];

  const fulfillmentColumns = [
    { key: 'order_number', header: 'Order', sortable: true, render: (r) => <span className="mono">{r.order_number}</span> },
    { key: 'status', header: 'Status', sortable: true, render: (r) => <StatusBadge status={r.status} /> },
    { key: 'required_date', header: 'Required', sortable: true, render: (r) => formatDate(r.required_date) },
    { key: 'ordered', header: 'Ordered', align: 'right', sortable: true, render: (r) => formatNumber(r.ordered) },
    { key: 'delivered', header: 'Delivered', align: 'right', sortable: true, render: (r) => formatNumber(r.delivered) },
    { key: 'percent', header: 'Fulfilled', sortable: true, className: 'progress-cell', render: (r) => (
      <div className="row" style={{ flexWrap: 'nowrap' }}>
        <ProgressBar value={r.percent} label={`${r.order_number} fulfilled`} tone={r.percent >= 100 ? 'green' : 'blue'} />
        <span className="small muted">{formatPercent(r.percent)}</span>
      </div>
    ) },
  ];

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Sales, production, quality and fulfillment performance computed from live data."
        actions={<Button icon="refresh" onClick={reloadAll}>Refresh</Button>}
      />

      <div className="stack">
        <Card title="Orders by customer" subtitle="Excludes cancelled and rejected orders">
          <FiltersBar onReset={range.date_from || range.date_to ? () => setRange({ date_from: '', date_to: '' }) : undefined}>
            <FilterDate label="Orders from" value={range.date_from} onChange={(v) => setRange((r) => ({ ...r, date_from: v }))} />
            <FilterDate label="Orders to" value={range.date_to} onChange={(v) => setRange((r) => ({ ...r, date_to: v }))} />
          </FiltersBar>
          {rangeInvalid ? <p className="small tone-text-amber">The start date is after the end date, so no orders can match.</p> : null}
          <Section state={customers}>
            {(rows) => {
              if (!rows.length) return <EmptyState title="No orders in this range" />;
              const top = rows.slice(0, 10).map((r) => ({ name: r.customer, value: toNumber(r.total_value) || 0 }));
              return (
                <div className="dash-grid">
                  <div className="col-6">
                    <div className="chart-box">
                      <ResponsiveContainer>
                        <BarChart data={top} layout="vertical" margin={{ left: 24, right: 16 }}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                          <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => formatNumber(v, { maxDecimals: 0 })} />
                          <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                          <Tooltip formatter={(v) => formatMoney(v)} />
                          <Bar dataKey="value" name="Order value" fill="#2557c7" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    {rows.length > 10 ? <p className="small muted">Top 10 of {rows.length} customers by order value.</p> : null}
                  </div>
                  <div className="col-6">
                    <DataTable columns={customerColumns} rows={rows} rowKey="customer_id" dense loading={customers.loading} />
                  </div>
                </div>
              );
            }}
          </Section>
        </Card>

        <Card title="Production performance" subtitle="Completed production jobs (latest 50 listed)">
          <Section state={production}>
            {(p) => (
              <div className="stack">
                <div className="kpi-grid">
                  <KpiCard label="Completed jobs" value={formatNumber(p.completed_jobs)} />
                  <KpiCard label="On-time jobs" value={formatNumber(p.on_time_jobs)} />
                  <KpiCard label="On-time rate" value={formatPercent(p.on_time_rate)} tone={pctTone(p.on_time_rate, 90, 75)} />
                  <KpiCard label="Units processed" value={formatNumber(p.units_processed)} />
                  <KpiCard label="Units rejected" value={formatNumber(p.units_rejected)} tone={toNumber(p.units_rejected) > 0 ? 'red' : undefined} />
                  <KpiCard label="Yield" value={formatPercent(p.yield_rate)} tone={pctTone(p.yield_rate, 95, 85)} />
                </div>
                <DataTable columns={jobColumns} rows={p.jobs} rowKey="job_number" dense emptyTitle="No completed jobs yet" />
              </div>
            )}
          </Section>
        </Card>

        <div className="dash-grid" style={{ marginTop: 0 }}>
          <div className="col-5">
            <Card title="Quality">
              <Section state={quality}>
                {(qr) => {
                  if (!qr.inspections) return <EmptyState title="No inspections recorded" />;
                  const outcomes = [
                    { name: 'Pass', count: qr.passed, fill: '#16a34a' },
                    { name: 'Fail', count: qr.failed, fill: '#dc2626' },
                    { name: 'Other', count: qr.inspections - qr.passed - qr.failed, fill: '#d97706' },
                  ].filter((o) => o.count > 0);
                  return (
                    <div className="stack">
                      <div className="kpi-grid">
                        <KpiCard label="Inspections" value={formatNumber(qr.inspections)} />
                        <KpiCard label="Units inspected" value={formatNumber(qr.units_inspected)} />
                        <KpiCard label="Defect units" value={formatNumber(qr.defect_units)} />
                        <KpiCard label="Defect rate" value={formatPercent(qr.defect_rate, { decimals: 2 })} tone={toNumber(qr.defect_rate) > 5 ? 'red' : toNumber(qr.defect_rate) > 2 ? 'amber' : 'green'} />
                      </div>
                      <div className="chart-box" style={{ height: 180 }}>
                        <ResponsiveContainer>
                          <BarChart data={outcomes} margin={{ right: 8 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Bar dataKey="count" name="Inspections" radius={[4, 4, 0, 0]}>
                              {outcomes.map((o) => <Cell key={o.name} fill={o.fill} />)}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  );
                }}
              </Section>
            </Card>
          </div>
          <div className="col-7">
            <Card title="Order fulfillment" subtitle="Open and fulfilled orders, by required date">
              <Section state={fulfillment}>
                {(rows) => (
                  <DataTable columns={fulfillmentColumns} rows={rows} rowKey="order_number" dense emptyTitle="No open orders" />
                )}
              </Section>
            </Card>
          </div>
        </div>
      </div>
    </>
  );
}
