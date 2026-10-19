import { useState } from 'react';
import Icon from './Icon';

/** On phones only the search box shows until "Filters" is tapped (see .filters-bar in components.css). */
export default function FiltersBar({ children, onReset }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`filters-bar ${open ? 'open' : ''}`} role="search">
      {children}
      <button type="button" className="btn btn-secondary btn-sm filters-toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Icon name="list" size={14} />
        {open ? 'Hide filters' : 'Filters'}
      </button>
      {onReset ? (
        <button type="button" className="btn btn-ghost btn-sm filters-reset" onClick={onReset}>
          <Icon name="close" size={14} />
          Clear filters
        </button>
      ) : null}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = 'Search…', label = 'Search' }) {
  return (
    <label className="search-input">
      <span className="sr-only">{label}</span>
      <Icon name="search" size={16} />
      <input type="search" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function FilterSelect({ label, value, onChange, options, allLabel = 'All' }) {
  return (
    <label className="filter-select">
      <span className="filter-label">{label}</span>
      <select value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((o) => {
          const opt = typeof o === 'object' ? o : { value: o, label: o };
          return <option key={opt.value} value={opt.value}>{opt.label}</option>;
        })}
      </select>
    </label>
  );
}

export function FilterDate({ label, value, onChange }) {
  return (
    <label className="filter-select">
      <span className="filter-label">{label}</span>
      <input type="date" value={value || ''} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function FilterToggle({ label, checked, onChange }) {
  return (
    <label className="filter-toggle">
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}
