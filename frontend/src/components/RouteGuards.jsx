import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Spinner from './Spinner';
import NoAccess from '../pages/NoAccess';

export function RequireAuth({ children }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <div className="fullpage-center"><Spinner label="Restoring session…" /></div>;
  if (status !== 'authenticated') return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

export function RequirePermission({ perm, children }) {
  const { can } = useAuth();
  if (!can(perm)) return <NoAccess />;
  return children;
}
