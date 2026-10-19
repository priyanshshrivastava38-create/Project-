import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/Toast';
import Icon from '../components/Icon';
import CommandPalette from '../components/CommandPalette';
import { humanize } from '../utils/format';
import { NAV_GROUPS } from './navConfig';

export function Sidebar({ open, onNavigate }) {
  const { can } = useAuth();
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Main navigation">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 32 32" width="28" height="28"><rect width="32" height="32" rx="7" fill="currentColor" /><path d="M7 23V9l9 8 9-8v14" fill="none" stroke="#fff" strokeWidth="3" strokeLinejoin="round" /></svg>
        </span>
        <span className="brand-name">MetalFlow <span>ERP</span></span>
      </div>
      <nav className="nav">
        {NAV_GROUPS.map((g) => {
          const items = g.items.filter((i) => can(i.perm));
          if (!items.length) return null;
          return (
            <div key={g.label} className="nav-group">
              <div className="nav-group-label">{g.label}</div>
              <ul>
                {items.map((i) => (
                  <li key={i.to}>
                    <NavLink to={i.to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} onClick={onNavigate} title={i.label}>
                      <Icon name={i.icon} />
                      <span>{i.label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('mf.sidebarCollapsed') === '1'; } catch { return false; }
  });

  useEffect(() => { setOpen(false); }, [location.pathname]);
  useEffect(() => {
    try { localStorage.setItem('mf.sidebarCollapsed', collapsed ? '1' : '0'); } catch { /* storage unavailable */ }
  }, [collapsed]);
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPaletteOpen((o) => !o); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Below 1100px the sidebar is an overlay drawer; above it the same button collapses it to icons.
  const toggleNav = () => {
    if (window.matchMedia('(max-width: 1100px)').matches) setOpen((o) => !o);
    else setCollapsed((c) => !c);
  };
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

  const onLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
      navigate('/login', { replace: true });
    } catch (e) {
      toast.error(e.message || 'Logout failed');
      navigate('/login', { replace: true });
    }
  };

  const initials = (user?.full_name || '?').split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <a href="#main" className="skip-link">Skip to content</a>
      <Sidebar open={open} onNavigate={() => setOpen(false)} />
      {open ? <div className="sidebar-scrim" onClick={() => setOpen(false)} aria-hidden="true" /> : null}
      <div className="app-main">
        <header className="topbar">
          <button type="button" className="icon-btn menu-btn" onClick={toggleNav} aria-label="Toggle navigation" aria-expanded={open || !collapsed}>
            <Icon name="menu" />
          </button>
          <button type="button" className="topbar-search" onClick={() => setPaletteOpen(true)}>
            <Icon name="search" size={16} />
            <span className="topbar-search-text">Search orders, jobs, customers…</span>
            <kbd className="hide-sm">{isMac ? '⌘' : 'Ctrl'} K</kbd>
          </button>
          <div className="topbar-spacer" />
          <div className="user-chip">
            <span className="avatar" aria-hidden="true">{initials}</span>
            <span className="user-meta">
              <span className="user-name">{user?.full_name}</span>
              <span className="user-role">{humanize(user?.role)}</span>
            </span>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onLogout} disabled={loggingOut}>
            <Icon name="logout" size={16} />
            <span className="hide-sm">Log out</span>
          </button>
        </header>
        <main id="main" className="content" tabIndex={-1}>
          <Outlet />
        </main>
        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      </div>
    </div>
  );
}
