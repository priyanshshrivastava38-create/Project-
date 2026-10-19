import { api } from './client';

export const listMaterials = (params) => api.get('/materials', params);
export const listMaterialCategories = () => api.get('/materials/categories');
export const createMaterial = (data) => api.post('/materials', data);
export const updateMaterial = (id, data) => api.patch(`/materials/${id}`, data);

export const listProducts = (params = { active: true }) => api.get('/products', params);
export const getProduct = (id) => api.get(`/products/${id}`);

export const listStages = () => api.get('/stages');
export const listWarehouses = () => api.get('/warehouses');

/** Fetch every page of a paginated endpoint (used for select options). */
export async function fetchAll(fn, params = {}, pageSize = 200) {
  let page = 1;
  const items = [];
  for (;;) {
    const res = await fn({ ...params, page, page_size: pageSize });
    items.push(...res.items);
    if (items.length >= res.total || res.items.length === 0) break;
    page += 1;
  }
  return items;
}
