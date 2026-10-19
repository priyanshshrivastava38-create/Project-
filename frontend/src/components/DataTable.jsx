import { useMemo, useState } from 'react';
import Icon from './Icon';
import Spinner from './Spinner';
import { EmptyState, ErrorState } from './States';

/**
 * columns: [{ key, header, render?(row), sortable?, sortValue?(row), align?, width?, className? }]
 * Sorting: client-side by default. Pass `sort` + `onSortChange` for server-side sorting
 * (sort is "field" or "-field").
 * Pagination: pass `page`, `pageSize`, `total`, `onPageChange` (and optional `onPageSizeChange`).
 */
export default function DataTable({
  columns, rows, rowKey = 'id', loading = false, error, onRetry, emptyTitle = 'No records found',
  emptyMessage, onRowClick, rowClassName, sort, onSortChange, page, pageSize, total, onPageChange,
  onPageSizeChange, caption, dense = false, renderExpanded,
}) {
  const [localSort, setLocalSort] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set());
  const serverSort = typeof onSortChange === 'function';
  const activeSort = serverSort ? sort : localSort;

  const sortedRows = useMemo(() => {
    if (!rows) return [];
    if (serverSort || !localSort) return rows;
    const desc = localSort.startsWith('-');
    const key = localSort.replace(/^-/, '');
    const col = columns.find((c) => c.key === key);
    if (!col) return rows;
    const get = col.sortValue || ((r) => r[key]);
    return [...rows].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      const na = Number(va);
      const nb = Number(vb);
      let cmp;
      if (va !== null && vb !== null && va !== '' && vb !== '' && !Number.isNaN(na) && !Number.isNaN(nb)) cmp = na - nb;
      else cmp = String(va ?? '').localeCompare(String(vb ?? ''));
      return desc ? -cmp : cmp;
    });
  }, [rows, localSort, serverSort, columns]);

  const toggleSort = (col) => {
    const key = col.sortKey || col.key;
    const next = activeSort === key ? `-${key}` : activeSort === `-${key}` ? null : key;
    if (serverSort) onSortChange(next);
    else setLocalSort(next);
  };

  const toggleExpand = (k) => setExpanded((s) => {
    const n = new Set(s);
    if (n.has(k)) n.delete(k); else n.add(k);
    return n;
  });

  const keyOf = (row, i) => (typeof rowKey === 'function' ? rowKey(row) : row[rowKey] ?? i);
  const showPager = typeof onPageChange === 'function' && total !== undefined;
  const pages = showPager ? Math.max(1, Math.ceil(total / pageSize)) : 1;

  let body;
  if (error && !rows?.length) {
    body = <ErrorState error={error} onRetry={onRetry} />;
  } else if (loading && !rows) {
    body = <Spinner />;
  } else if (!sortedRows.length) {
    body = loading ? <Spinner /> : <EmptyState title={emptyTitle} message={emptyMessage} />;
  }

  return (
    <div className={`table-card ${loading && rows ? 'is-refreshing' : ''}`}>
      {body || (
        <div className="table-scroll">
          <table className={`table ${dense ? 'table-dense' : ''}`}>
            {caption ? <caption className="sr-only">{caption}</caption> : null}
            <thead>
              <tr>
                {renderExpanded ? <th className="col-expand"><span className="sr-only">Expand</span></th> : null}
                {columns.map((c) => {
                  const key = c.sortKey || c.key;
                  const dir = activeSort === key ? 'ascending' : activeSort === `-${key}` ? 'descending' : 'none';
                  return (
                    <th key={c.key} style={{ width: c.width, textAlign: c.align }} aria-sort={c.sortable ? dir : undefined} className={c.className}>
                      {c.sortable ? (
                        <button type="button" className="th-sort" onClick={() => toggleSort(c)}>
                          {c.header}
                          <Icon name={dir === 'ascending' ? 'sortAsc' : dir === 'descending' ? 'sortDesc' : 'sort'} size={14} />
                        </button>
                      ) : c.header}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row, i) => {
                const k = keyOf(row, i);
                const isOpen = expanded.has(k);
                return [
                  <tr
                    key={k}
                    className={`${onRowClick ? 'row-click' : ''} ${rowClassName ? rowClassName(row) || '' : ''}`}
                    onClick={onRowClick ? (e) => { if (!e.target.closest('button, a, input, select, label')) onRowClick(row); } : undefined}
                    onKeyDown={onRowClick ? (e) => { if (e.key === 'Enter' && e.target === e.currentTarget) onRowClick(row); } : undefined}
                    tabIndex={onRowClick ? 0 : undefined}
                  >
                    {renderExpanded ? (
                      <td className="col-expand">
                        <button type="button" className="icon-btn" aria-expanded={isOpen} aria-label={isOpen ? 'Collapse row' : 'Expand row'} onClick={() => toggleExpand(k)}>
                          <Icon name={isOpen ? 'chevronDown' : 'chevronRight'} size={14} />
                        </button>
                      </td>
                    ) : null}
                    {columns.map((c) => (
                      <td key={c.key} style={{ textAlign: c.align }} className={c.className}>
                        {c.render ? c.render(row) : row[c.key] ?? '—'}
                      </td>
                    ))}
                  </tr>,
                  renderExpanded && isOpen ? (
                    <tr key={`${k}-x`} className="row-expanded">
                      <td colSpan={columns.length + 1}>{renderExpanded(row)}</td>
                    </tr>
                  ) : null,
                ];
              })}
            </tbody>
          </table>
        </div>
      )}
      {showPager && total > 0 ? (
        <div className="pager">
          <span className="pager-info">
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
          </span>
          {onPageSizeChange ? (
            <label className="pager-size">
              <span>Rows</span>
              <select value={pageSize} onChange={(e) => onPageSizeChange(Number(e.target.value))}>
                {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          ) : null}
          <div className="pager-btns">
            <button type="button" className="icon-btn" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label="Previous page">
              <Icon name="chevronLeft" />
            </button>
            <span className="pager-page">Page {page} of {pages}</span>
            <button type="button" className="icon-btn" onClick={() => onPageChange(page + 1)} disabled={page >= pages} aria-label="Next page">
              <Icon name="chevronRight" />
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
