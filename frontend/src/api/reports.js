import { api } from './client';

export const ordersByCustomer = (params) => api.get('/reports/orders-by-customer', params);
export const productionPerformance = () => api.get('/reports/production-performance');
export const qualityReport = () => api.get('/reports/quality');
export const fulfillmentReport = () => api.get('/reports/fulfillment');
export const listAuditLogs = (params) => api.get('/audit-logs', params);
