import { api } from './client';

export const listJobs = (params) => api.get('/production/jobs', params);
export const getBoard = () => api.get('/production/board');
export const getJob = (id) => api.get(`/production/jobs/${id}`);
export const createJob = (data) => api.post('/production/jobs', data);
export const updateJob = (id, data) => api.patch(`/production/jobs/${id}`, data);
export const allocateMaterials = (id, data = {}) => api.post(`/production/jobs/${id}/allocate-materials`, data);
export const startJob = (id) => api.post(`/production/jobs/${id}/start`);
export const advanceJob = (id, notes) => api.post(`/production/jobs/${id}/advance`, { notes: notes || null });
export const recordOutput = (id, data) => api.post(`/production/jobs/${id}/record-output`, data);
export const completeJob = (id) => api.post(`/production/jobs/${id}/complete`);
export const cancelJob = (id, reason) => api.post(`/production/jobs/${id}/cancel`, { reason });
