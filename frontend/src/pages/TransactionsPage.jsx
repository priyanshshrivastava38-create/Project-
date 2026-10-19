import { useEffect, useState } from 'react';
import { listTransactions } from '../api/inventory';
import { listWarehouses } from '../api/catalog';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { DataTable, FilterSelect, FiltersBar, PageHeader, SearchInput, StatusBadge } from '../components';
import { formatDateTime, formatNumber, humanize, toNumber } from '../utils/format';
import { TXN_TYPES } from '../utils/status';
import InventoryTabs from './InventoryTabs';

function Delta({ value }) {
  const n = toNumber(value) || 0;
  if (n === 0) return <span className="muted">0</span>;
  return <span className={n > 0 ? 'tone-text-green' : 'tone-text-red'}>{n > 0 ? '+' : ''}{formatNumber(value)}</span>;
}

export default function TransactionsPage() {
  const pg = usePagination({ txn_type: '', warehouse_id: '' });
  const [search, setSearch] = useState('');
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, error, loading, reload } = useAsync(
    () => listTransactions({ ...pg.params, q }),
    [pg.page, pg.pageSize, pg.filters.txn_type, pg.filters.warehouse_id, q],
  );
  const warehouses = useAsync(() => listWarehouses(), []);

  const columns = [
    { key: 'created_at', header: 'When', render: (r) => <span className="nowrap">{formatDateTime(r.created_at)}</span> },
    { key: 'txn_type', header: 'Type', render: (r) => <StatusBadge status={r.txn_type} /> },
    { key: 'item', header: 'Item', render: (r) => {
      const it = r.balance.material || r.balance.product;
      return <div><div className="mono">{it?.sku}</div><div className="small muted">{it?.name}</div></div>;
    } },
    { key: 'warehouse', header: 'Warehouse', render: (r) => r.balance.warehouse.code },
    { key: 'on_hand_delta', header: 'On-hand Δ', align: 'right', render: (r) => <Delta value={r.on_hand_delta} /> },
    { key: 'reserved_delta', header: 'Reserved Δ', align: 'right', render: (r) => <Delta value={r.reserved_delta} /> },
    { key: 'on_hand_after', header: 'On hand after', align: 'right', render: (r) => formatNumber(r.on_hand_after) },
    { key: 'reference', header: 'Reference', render: (r) => (r.reference_type ? <span className="small">{humanize(r.reference_type)} #{r.reference_id}</span> : '—') },
    { key: 'reason', header: 'Reason', render: (r) => <span className="small">{r.reason || '—'}</span> },
    { key: 'user', header: 'By', render: (r) => r.user?.full_name || '—' },
  ];

  return (
    <>
      <PageHeader title="Inventory" subtitle="Immutable ledger of every stock movement." />
      <InventoryTabs />
      <FiltersBar onReset={() => { setSearch(''); pg.resetFilters(); }}>
        <SearchInput value={search} onChange={setSearch} placeholder="SKU, name or reason…" />
        <FilterSelect label="Type" value={pg.filters.txn_type} onChange={(v) => pg.setFilter('txn_type', v)} options={TXN_TYPES.map((t) => ({ value: t, label: humanize(t) }))} />
        <FilterSelect label="Warehouse" value={pg.filters.warehouse_id} onChange={(v) => pg.setFilter('warehouse_id', v)} options={(warehouses.data || []).map((w) => ({ value: String(w.id), label: `${w.code} · ${w.name}` }))} />
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
        dense
        emptyTitle="No transactions match"
      />
    </>
  );
}
