import { Link } from 'react-router-dom';

export default function PageHeader({ title, subtitle, actions, breadcrumbs, meta }) {
  return (
    <header className="page-header">
      <div className="page-header-main">
        {breadcrumbs?.length ? (
          <nav aria-label="Breadcrumb" className="breadcrumbs">
            {breadcrumbs.map((b, i) => (
              <span key={b.label}>
                {b.to ? <Link to={b.to}>{b.label}</Link> : <span>{b.label}</span>}
                {i < breadcrumbs.length - 1 ? <span className="sep" aria-hidden="true">/</span> : null}
              </span>
            ))}
          </nav>
        ) : null}
        <div className="page-title-row">
          <h1 className="page-title">{title}</h1>
          {meta}
        </div>
        {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}
