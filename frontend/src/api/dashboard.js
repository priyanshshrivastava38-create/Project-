import { api } from './client';

export const getSummary = (params) => api.get('/dashboard/summary', params);
export const getProductionTrend = (days) => api.get('/dashboard/production', { days });
export const getInventoryAlerts = () => api.get('/dashboard/inventory-alerts');
