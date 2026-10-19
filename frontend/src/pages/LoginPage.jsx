import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Button from '../components/Button';
import FormField from '../components/FormField';
import { Alert } from '../components/States';
import Spinner from '../components/Spinner';
import Icon from '../components/Icon';

// Seeded demo accounts (scripts/seed.py); offered only in local development builds.
const DEMO_ACCOUNTS = import.meta.env.DEV
  ? [['admin', 'Admin'], ['sales', 'Sales'], ['production', 'Production'], ['quality', 'Quality'], ['inventory', 'Inventory'], ['dispatch', 'Dispatch']]
  : [];

export default function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const from = location.state?.from?.pathname && location.state.from.pathname !== '/login'
    ? location.state.from.pathname + (location.state.from.search || '')
    : '/';

  if (status === 'loading') return <div className="fullpage-center"><Spinner label="Checking session…" /></div>;
  if (status === 'authenticated') return <Navigate to={from} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setPending(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.status === 401 || err.status === 429 ? (err.message || 'Invalid email or password') : (err.message || 'Login failed'));
      setPending(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand brand-login">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="34" height="34"><rect width="32" height="32" rx="7" fill="currentColor" /><path d="M7 23V9l9 8 9-8v14" fill="none" stroke="#fff" strokeWidth="3" strokeLinejoin="round" /></svg>
          </span>
          <span className="brand-name">MetalFlow <span>ERP</span></span>
        </div>
        <h1 className="login-title">Sign in</h1>
        <p className="muted">Manufacturing operations, from order to delivery.</p>
        <form onSubmit={submit} className="stack" noValidate>
          <FormField label="Email" required>
            <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
          </FormField>
          <div className="password-field">
            <FormField label="Password" required>
              <input type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </FormField>
            <button type="button" className="link-btn small password-toggle" onClick={() => setShowPassword((v) => !v)} aria-pressed={showPassword}>
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
          {error ? <Alert>{error}</Alert> : null}
          <Button type="submit" variant="primary" loading={pending} disabled={!email || !password} className="btn-block">
            Sign in
          </Button>
        </form>
        {DEMO_ACCOUNTS.length ? (
          <div className="demo-accounts">
            <div className="small muted"><Icon name="info" size={14} /> Demo accounts (local dev). Click to fill in, then sign in.</div>
            <div className="row">
              {DEMO_ACCOUNTS.map(([key, label]) => (
                <button key={key} type="button" className="chip-btn" onClick={() => { setEmail(`${key}@metalflow.example`); setPassword('MetalFlow-demo-2026'); }}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
