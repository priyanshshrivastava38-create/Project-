import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { listOrders } from '../api/orders';
import { listCustomers } from '../api/customers';
import { fetchAll } from '../api/catalog';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { useAuth } from '../context/AuthContext';
import {
  Button, DataTable, FilterDate, FilterSelect, FiltersBar, PageHeader, SearchInput, StatusBadge,
} from '../components';
import { formatDate, humanize, formatMoney } from '../utils/format';
import { ORDER_STATUSES } from '../utils/status';

export default function OrdersPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initial = { status: params.get('status') || '', customer_id: params.get('customer_id') || '', date_from: '', date_to: '' };
  const pg = usePagination(initial);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('-order_date');
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, error, loading, reload } = useAsync(
    () => listOrders({ ...pg.params, q, sort }),
    [pg.page, pg.pageSize, pg.filters.status, pg.filters.customer_id, pg.filters.date_from, pg.filters.date_to, q, sort],
  );
  const customers = useAsync(() => fetchAll(listCustomers), [], { enabled: can('customers:read') });

  const columns = [
    { key: 'order_number', header: 'Order', sortable: true, render: (r) => <strong>{r.order_number}</strong> },
    { key: 'customer', header: 'Customer', render: (r) => r.customer?.company_name },
    { key: 'order_date', header: 'Order date', sortable: true, render: (r) => formatDate(r.order_date) },
    { key: 'required_date', header: 'Required', sortable: true, render: (r) => formatDate(r.required_date) },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'total', header: 'Total', sortable: true, align: 'right', render: (r) => formatMoney(r.total, r.currency) },
  ];

  return (
    <>
      <PageHeader
        title="Sales orders"
        subtitle="Track orders from draft to fulfilment."
        actions={can('orders:write') ? <Button variant="primary" icon="plus" onClick={() => navigate('/orders/new')}>New order</Button> : null}
      />
      <FiltersBar onReset={() => { setSearch(''); pg.setFilters({ status: '', customer_id: '', date_from: '', date_to: '' }); }}>
        <SearchInput value={search} onChange={setSearch} placeholder="Order number or customer…" />
        <FilterSelect label="Status" value={pg.filters.status} onChange={(v) => pg.setFilter('status', v)} options={ORDER_STATUSES.map((s) => ({ value: s, label: humanize(s) }))} />
        {can('customers:read') ? (
          <FilterSelect label="Customer" value={pg.filters.customer_id} onChange={(v) => pg.setFilter('customer_id', v)} options={(customers.data || []).map((c) => ({ value: String(c.id), label: c.company_name }))} />
        ) : null}
        <FilterDate label="From" value={pg.filters.date_from} onChange={(v) => pg.setFilter('date_from', v)} />
        <FilterDate label="To" value={pg.filters.date_to} onChange={(v) => pg.setFilter('date_to', v)} />
      </FiltersBar>
      <DataTable
        columns={columns}
        rows={data?.items}
        loading={loading}
        error={error}
        onRetry={reload}
        sort={sort}
        onSortChange={(s) => { setSort(s || '-order_date'); pg.setPage(1); }}
        page={pg.page}
        pageSize={pg.pageSize}
        total={data?.total}
        onPageChange={pg.setPage}
        onPageSizeChange={pg.setPageSize}
        onRowClick={(r) => navigate(`/orders/${r.id}`)}
        emptyTitle="No orders match these filters"
      />
    </>
  );
}
