import { api } from './client';

export const chat = (question) => api.post('/assistant/chat', { question });
export const getAssistantHistory = () => api.get('/assistant/history');
export const getAssistantHealth = () => api.get('/assistant/health');
