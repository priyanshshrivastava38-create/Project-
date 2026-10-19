import { api, request } from './client';

export const login = (email, password) =>
  request('/auth/login', { method: 'POST', body: { email, password }, skipAuth: true });
export const logout = () => request('/auth/logout', { method: 'POST', skipAuth: true });
export const getMe = () => api.get('/auth/me');
