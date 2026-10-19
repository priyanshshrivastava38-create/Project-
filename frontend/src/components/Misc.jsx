import { NavLink } from 'react-router-dom';
import { formatDateTime, humanize } from '../utils/format';
import StatusBadge from './StatusBadge';

export function Card({ title, actions, children, className = '', padded = true, subtitle }) {
  return (
    <section className={`card ${className}`}>
      {title || actions ? (
        <div className="card-header">
          <div>
            {title ? <h2 className="card-title">{title}</h2> : null}
            {subtitle ? <p className="card-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="card-actions">{actions}</div> : null}
        </div>
      ) : null}
      <div className={padded ? 'card-body' : ''}>{children}</div>
    </section>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        t.to ? (
          <NavLink key={t.value} to={t.to} end className={({ isActive }) => `tab ${isActive ? 'active' : ''}`}>{t.label}</NavLink>
        ) : (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={value === t.value}
            className={`tab ${value === t.value ? 'active' : ''}`}
            onClick={() => onChange(t.value)}
          >
            {t.label}
          </button>
        )
      ))}
    </div>
  );
}

export function ProgressBar({ value, max = 100, label, tone = 'blue' }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (Number(value) / Number(max)) * 100)) : 0;
  return (
    <div className="progress" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className={`progress-fill tone-${tone}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function KeyValue({ items }) {
  return (
    <dl className="kv">
      {items.filter(Boolean).map(([k, v]) => (
        <div key={k} className="kv-row">
          <dt>{k}</dt>
          <dd>{v === null || v === undefined || v === '' ? '—' : v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Vertical timeline of status changes. entries: [{status, from, title, note, by, at}] */
export function Timeline({ entries }) {
  if (!entries?.length) return <p className="muted">No history yet.</p>;
  return (
    <ol className="timeline">
      {entries.map((e, i) => (
        <li key={i} className="timeline-item">
          <span className={`timeline-dot dot-${e.tone || 'blue'}`} aria-hidden="true" />
          <div className="timeline-content">
            <div className="timeline-head">
              {e.status ? <StatusBadge status={e.status} /> : <strong>{e.title}</strong>}
              {e.from ? <span className="muted small">from {humanize(e.from)}</span> : null}
            </div>
            {e.note ? <div className="timeline-note">{e.note}</div> : null}
            <div className="muted small">{[e.by, formatDateTime(e.at)].filter(Boolean).join(' · ')}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function KpiCard({ label, value, hint, tone, to, icon }) {
  const content = (
    <>
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value ${tone ? `tone-text-${tone}` : ''}`}>{value}</div>
      {hint ? <div className="kpi-hint">{hint}</div> : null}
      {icon}
    </>
  );
  return to ? <NavLink to={to} className="kpi-card kpi-link">{content}</NavLink> : <div className="kpi-card">{content}</div>;
}
