import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { listInventory } from '../api/inventory';
import { fetchAll, listMaterialCategories, listWarehouses } from '../api/catalog';
import { listSuppliers } from '../api/suppliers';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useDebounced } from '../hooks/useDebounced';
import { useAuth } from '../context/AuthContext';
import {
  Button, DataTable, FilterSelect, FilterToggle, FiltersBar, PageHeader, SearchInput, StatusBadge,
} from '../components';
import { formatDate, formatDateTime, formatNumber } from '../utils/format';
import InventoryTabs from './InventoryTabs';
import { AdjustModal, ReceiveModal } from './InventoryModals';

export default function InventoryPage() {
  const { can } = useAuth();
  const [params] = useSearchParams();
  const pg = usePagination({ item_type: '', category: '', warehouse_id: '', supplier_id: '', low_stock: params.get('low_stock') === 'true' });
  const [search, setSearch] = useState('');
  const q = useDebounced(search);
  useEffect(() => { pg.setPage(1); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const f = pg.filters;
  const { data, error, loading, reload } = useAsync(
    () => listInventory({ ...pg.params, q, low_stock: f.low_stock || undefined }),
    [pg.page, pg.pageSize, f.item_type, f.category, f.warehouse_id, f.supplier_id, f.low_stock, q],
  );
  const categories = useAsync(() => listMaterialCategories(), [], { enabled: can('products:read') });
  const warehouses = useAsync(() => listWarehouses(), []);
  const suppliers = useAsync(() => fetchAll(listSuppliers), [], { enabled: can('suppliers:read') });
  const [receive, setReceive] = useState(null);
  const [adjust, setAdjust] = useState(null);

  const columns = [
    { key: 'item', header: 'Item', sortable: true, sortValue: (r) => (r.material || r.product)?.sku, render: (r) => {
      const it = r.material || r.product;
      return <div><div className="mono">{it?.sku}</div><div className="small muted">{it?.name}</div></div>;
    } },
    { key: 'item_type', header: 'Type', render: (r) => <StatusBadge status={r.item_type} /> },
    { key: 'category', header: 'Category', render: (r) => r.category || '—' },
    { key: 'warehouse', header: 'Warehouse', render: (r) => <span title={r.warehouse.name}>{r.warehouse.code}</span> },
    { key: 'on_hand', header: 'On hand', align: 'right', sortable: true, render: (r) => formatNumber(r.on_hand) },
    { key: 'reserved', header: 'Reserved', align: 'right', sortable: true, render: (r) => formatNumber(r.reserved) },
    { key: 'available', header: 'Available', align: 'right', sortable: true, render: (r) => (
      <div className="nowrap">
        <strong className={r.low_stock ? 'tone-text-red' : ''}>{formatNumber(r.available)}</strong>{' '}
        <span className="small muted">{(r.material || r.product)?.uom}</span>
        {r.low_stock ? <div><StatusBadge status="LOW" label="Low stock" tone="red" /></div> : null}
      </div>
    ) },
    { key: 'reorder_level', header: 'Reorder lvl', align: 'right', render: (r) => (r.reorder_level !== null ? formatNumber(r.reorder_level) : '—') },
    { key: 'updated_at', header: 'Updated', render: (r) => <span className="small muted nowrap" title={formatDateTime(r.updated_at)}>{formatDate(r.updated_at)}</span> },
    (can('inventory:receive') || can('inventory:adjust')) ? { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="row" style={{ justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
        {can('inventory:receive') && r.material ? <Button size="sm" variant="ghost" onClick={() => setReceive({ material_id: r.material.id, warehouse_id: r.warehouse.id })}>Receive</Button> : null}
        {can('inventory:adjust') ? <Button size="sm" variant="ghost" onClick={() => setAdjust({ item_type: r.item_type, item_id: (r.material || r.product).id, warehouse_id: r.warehouse.id })}>Adjust</Button> : null}
      </div>
    ) } : null,
  ].filter(Boolean);

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle="Stock on hand, reservations and availability per warehouse."
        actions={(
          <>
            {can('inventory:adjust') ? <Button onClick={() => setAdjust({})}>Adjust stock</Button> : null}
            {can('inventory:receive') ? <Button variant="primary" icon="plus" onClick={() => setReceive({})}>Receive material</Button> : null}
          </>
        )}
      />
      <InventoryTabs />
      <FiltersBar onReset={() => { setSearch(''); pg.resetFilters(); pg.setFilter('low_stock', false); }}>
        <SearchInput value={search} onChange={setSearch} placeholder="SKU or name…" />
        <FilterSelect label="Item type" value={f.item_type} onChange={(v) => pg.setFilter('item_type', v)} options={[{ value: 'MATERIAL', label: 'Material' }, { value: 'PRODUCT', label: 'Product' }]} />
        {categories.data ? <FilterSelect label="Category" value={f.category} onChange={(v) => pg.setFilter('category', v)} options={categories.data} /> : null}
        <FilterSelect label="Warehouse" value={f.warehouse_id} onChange={(v) => pg.setFilter('warehouse_id', v)} options={(warehouses.data || []).map((w) => ({ value: String(w.id), label: `${w.code} · ${w.name}` }))} />
        {can('suppliers:read') ? <FilterSelect label="Supplier" value={f.supplier_id} onChange={(v) => pg.setFilter('supplier_id', v)} options={(suppliers.data || []).map((s) => ({ value: String(s.id), label: s.company_name }))} /> : null}
        <FilterToggle label="Low stock only" checked={f.low_stock} onChange={(v) => pg.setFilter('low_stock', v)} />
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
        rowClassName={(r) => (r.low_stock ? 'row-warn' : '')}
        emptyTitle="No stock records match"
      />
      <ReceiveModal open={!!receive} preset={receive} warehouses={warehouses.data} onClose={() => setReceive(null)} onDone={() => { setReceive(null); reload(); }} />
      <AdjustModal open={!!adjust} preset={adjust} warehouses={warehouses.data} onClose={() => setAdjust(null)} onDone={() => { setAdjust(null); reload(); }} />
    </>
  );
}
