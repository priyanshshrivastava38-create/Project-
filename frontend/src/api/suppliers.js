import { api } from './client';

export const listSuppliers = (params) => api.get('/suppliers', params);
export const getSupplier = (id) => api.get(`/suppliers/${id}`);
export const createSupplier = (data) => api.post('/suppliers', data);
export const updateSupplier = (id, data) => api.patch(`/suppliers/${id}`, data);
