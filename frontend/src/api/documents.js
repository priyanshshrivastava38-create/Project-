import { api, request } from './client';

export const listDocuments = (params) => api.get('/documents', params);
export const getDocument = (id) => api.get(`/documents/${id}`);
export const uploadDocument = (formData) => api.upload('/documents', formData);
export const approveDocument = (id, data = {}) => api.post(`/documents/${id}/approve`, data);
export const archiveDocument = (id, data = {}) => api.post(`/documents/${id}/archive`, data);
export const listApprovals = (id) => api.get(`/documents/${id}/approvals`);

function filenameFrom(res, fallback) {
  const cd = res.headers.get('content-disposition') || '';
  const star = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  if (star) return decodeURIComponent(star[1]);
  const plain = /filename="?([^";]+)"?/i.exec(cd);
  return plain ? plain[1] : fallback;
}

/** Download a document version with the bearer token, then trigger a browser download. */
export async function downloadDocument(id, versionId, fallbackName = 'document') {
  const res = await request(`/documents/${id}/download`, {
    query: versionId ? { version_id: versionId } : undefined,
    raw: true,
    headers: { Accept: '*/*' },
  });
  const blob = await res.blob();
  const name = filenameFrom(res, fallbackName);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return name;
}
