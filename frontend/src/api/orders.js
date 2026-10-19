import { api } from './client';

export const listOrders = (params) => api.get('/orders', params);
export const getOrder = (id) => api.get(`/orders/${id}`);
export const createOrder = (data) => api.post('/orders', data);
export const updateOrder = (id, data) => api.patch(`/orders/${id}`, data);
export const confirmOrder = (id) => api.post(`/orders/${id}/confirm`);
export const cancelOrder = (id, reason) => api.post(`/orders/${id}/cancel`, { reason });
export const rejectOrder = (id, reason) => api.post(`/orders/${id}/reject`, { reason });
