import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useDebounced } from '../hooks/useDebounced';
import { NAV_GROUPS } from '../layouts/navConfig';
import { listCustomers } from '../api/customers';
import { listDeliveries } from '../api/deliveries';
import { listOrders } from '../api/orders';
import { listJobs } from '../api/production';
import { humanize } from '../utils/format';
import Icon from './Icon';
import Spinner from './Spinner';

/** Records searched as you type; each source only runs when the user may read it. */
const SOURCES = [
  { perm: 'orders:read', icon: 'orders', fetch: (q) => listOrders({ q, page_size: 5 }),
    map: (o) => ({ title: o.order_number, sub: `${o.customer?.company_name || ''} · ${humanize(o.status)}`, to: `/orders/${o.id}` }) },
  { perm: 'production:read', icon: 'production', fetch: (q) => listJobs({ q, page_size: 5 }),
    map: (j) => ({ title: j.job_number, sub: `${j.product?.sku || ''} · ${humanize(j.status)}`, to: `/production/jobs/${j.id}` }) },
  { perm: 'customers:read', icon: 'customers', fetch: (q) => listCustomers({ q, page_size: 5 }),
    map: (c) => ({ title: c.company_name, sub: c.code, to: `/customers/${c.id}` }) },
  { perm: 'deliveries:read', icon: 'deliveries', fetch: (q) => listDeliveries({ q, page_size: 5 }),
    map: (d) => ({ title: d.delivery_number, sub: `${d.customer_name} · ${humanize(d.status)}`, to: `/deliveries?q=${encodeURIComponent(d.delivery_number)}` }) },
];

export default function CommandPalette({ open, onClose }) {
  const { can } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [records, setRecords] = useState([]);
  const [searching, setSearching] = useState(false);
  const q = useDebounced(query.trim(), 250);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActive(0);
      setRecords([]);
    }
  }, [open]);

  useEffect(() => {
    if (!open || q.length < 2) { setRecords([]); return undefined; }
    let cancelled = false;
    setSearching(true);
    const sources = SOURCES.filter((s) => can(s.perm));
    Promise.allSettled(sources.map((s) => s.fetch(q))).then((results) => {
      if (cancelled) return;
      setRecords(results.flatMap((r, i) => (r.status === 'fulfilled' ? (r.value?.items || []).map((x) => ({ ...sources[i].map(x), icon: sources[i].icon })) : [])));
      setSearching(false);
    });
    return () => { cancelled = true; };
  }, [q, open, can]);

  const pages = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return NAV_GROUPS.flatMap((g) => g.items.filter((i) => can(i.perm)).map((i) => ({ title: i.label, sub: g.label, to: i.to, icon: i.icon })))
      .filter((p) => !needle || p.title.toLowerCase().includes(needle) || p.sub.toLowerCase().includes(needle));
  }, [query, can]);

  const items = [...records, ...pages];
  useEffect(() => { setActive(0); }, [items.length]);

  if (!open) return null;

  const go = (item) => { onClose(); navigate(item.to); };
  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === 'Enter' && items[active]) { e.preventDefault(); go(items[active]); }
    else if (e.key === 'Escape') onClose();
  };

  const renderItem = (item, idx) => (
    <li key={`${item.to}-${idx}`} role="option" aria-selected={idx === active}>
      <button type="button" className={`cmdk-item ${idx === active ? 'active' : ''}`} onMouseMove={() => { if (idx !== active) setActive(idx); }} onClick={() => go(item)}>
        <span className="cmdk-icon"><Icon name={item.icon} size={16} /></span>
        <span className="cmdk-text"><span className="cmdk-title">{item.title}</span><span className="cmdk-sub">{item.sub}</span></span>
        {idx === active ? <Icon name="chevronRight" size={14} /> : null}
      </button>
    </li>
  );

  return (
    <div className="modal-backdrop cmdk-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cmdk" role="dialog" aria-modal="true" aria-label="Search and jump">
        <div className="cmdk-input">
          <Icon name="search" size={18} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search orders, jobs, customers, deliveries… or jump to a page"
            aria-label="Search"
            role="combobox"
            aria-expanded="true"
          />
          {searching ? <Spinner size="sm" inline /> : <kbd>Esc</kbd>}
        </div>
        <ul className="cmdk-list" role="listbox">
          {records.length ? <li className="cmdk-group">Records</li> : null}
          {records.map((r, i) => renderItem(r, i))}
          {pages.length ? <li className="cmdk-group">Pages</li> : null}
          {pages.map((p, i) => renderItem(p, records.length + i))}
          {!items.length && !searching ? <li className="cmdk-empty">No matches for “{query}”</li> : null}
        </ul>
        <div className="cmdk-foot"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>Enter</kbd> open</span></div>
      </div>
    </div>
  );
}
