import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { refreshAccessToken, setAccessToken, setAuthFailureHandler } from '../api/client';
import * as authApi from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: 'loading', user: null });

  const loadMe = useCallback(async () => {
    const me = await authApi.getMe();
    setState({ status: 'authenticated', user: me });
    return me;
  }, []);

  // On app load: try to restore the session from the httpOnly refresh cookie.
  useEffect(() => {
    let cancelled = false;
    setAuthFailureHandler(() => {
      setAccessToken(null);
      setState({ status: 'anonymous', user: null });
    });
    (async () => {
      try {
        await refreshAccessToken();
        const me = await authApi.getMe();
        if (!cancelled) setState({ status: 'authenticated', user: me });
      } catch {
        if (!cancelled) {
          setAccessToken(null);
          setState({ status: 'anonymous', user: null });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const tokens = await authApi.login(email, password);
    setAccessToken(tokens.access_token);
    return loadMe();
  }, [loadMe]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setAccessToken(null);
      setState({ status: 'anonymous', user: null });
    }
  }, []);

  const value = useMemo(() => {
    const permissions = new Set(state.user?.permissions || []);
    const can = (perm) => {
      if (!perm) return true;
      if (Array.isArray(perm)) return perm.some((p) => permissions.has(p));
      return permissions.has(perm);
    };
    return { ...state, user: state.user, can, login, logout, reloadUser: loadMe };
  }, [state, login, logout, loadMe]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
