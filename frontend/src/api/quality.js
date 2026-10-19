import { api } from './client';

export const listInspections = (params) => api.get('/quality/inspections', params);
export const getInspection = (id) => api.get(`/quality/inspections/${id}`);
export const createInspection = (data) => api.post('/quality/inspections', data);
export const reinspect = (id, data) => api.post(`/quality/inspections/${id}/reinspect`, data);
