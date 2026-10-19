import { api } from './client';

export const listDeliveries = (params) => api.get('/deliveries', params);
export const listDispatchable = () => api.get('/deliveries/dispatchable');
export const getDelivery = (id) => api.get(`/deliveries/${id}`);
export const createDelivery = (data) => api.post('/deliveries', data);
export const markReady = (id) => api.post(`/deliveries/${id}/ready`);
export const dispatchDelivery = (id, data) => api.post(`/deliveries/${id}/dispatch`, data);
export const markInTransit = (id) => api.post(`/deliveries/${id}/in-transit`);
export const confirmDelivery = (id, data) => api.post(`/deliveries/${id}/confirm-delivery`, data);
export const failDelivery = (id, data) => api.post(`/deliveries/${id}/fail`, data);
export const cancelDelivery = (id, reason) => api.post(`/deliveries/${id}/cancel`, { reason });
