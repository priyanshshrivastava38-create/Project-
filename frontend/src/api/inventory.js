import { api } from './client';

const idem = (key) => ({ headers: { 'Idempotency-Key': key } });

export const listInventory = (params) => api.get('/inventory', params);
export const listLowStock = () => api.get('/inventory/low-stock');
export const listTransactions = (params) => api.get('/inventory/transactions', params);
export const receiveMaterial = (data, idempotencyKey) => api.post('/inventory/receipts', data, idem(idempotencyKey));
export const adjustStock = (data, idempotencyKey) => api.post('/inventory/adjustments', data, idem(idempotencyKey));
export const listReservations = (params) => api.get('/inventory/reservations', params);
export const releaseReservation = (id, reason) => api.post(`/inventory/reservations/${id}/release`, { reason });
