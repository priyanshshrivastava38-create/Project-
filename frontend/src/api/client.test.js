import { describe, expect, it, vi, beforeEach } from 'vitest';
import { api, buildQuery, errorMessage, fieldErrors, getAccessToken, setAccessToken, setAuthFailureHandler } from './client';

const json = (status, body) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('buildQuery', () => {
  it('drops empty values and joins arrays', () => {
    expect(buildQuery({ q: 'steel', page: 2, status: ['A', 'B'], empty: '', none: null, tags: [] })).toBe(
      '?q=steel&page=2&status=A%2CB',
    );
    expect(buildQuery({})).toBe('');
  });

  it('keeps active=false but drops other false flags', () => {
    expect(buildQuery({ active: false, archived: false })).toBe('?active=false');
  });
});

describe('request', () => {
  beforeEach(() => {
    setAccessToken('old');
    setAuthFailureHandler(null);
  });

  it('sends the bearer token and parses the error envelope', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      json(409, { error: { code: 'conflict', message: 'Duplicate SKU', details: null } }),
    );
    await expect(api.post('/materials', { sku: 'X' })).rejects.toMatchObject({ status: 409, code: 'conflict', message: 'Duplicate SKU' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/materials');
    expect(init.headers.Authorization).toBe('Bearer old');
    expect(init.body).toBe('{"sku":"X"}');
  });

  it('refreshes once on 401 and retries with the new token', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(json(401, { error: { code: 'not_authenticated', message: 'Expired' } }))
      .mockResolvedValueOnce(json(200, { access_token: 'new', expires_in: 900 }))
      .mockResolvedValueOnce(json(200, { ok: true }));
    await expect(api.get('/orders')).resolves.toEqual({ ok: true });
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/refresh');
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer new');
    expect(getAccessToken()).toBe('new');
  });

  it('calls the auth failure handler when refresh fails', async () => {
    const onFail = vi.fn();
    setAuthFailureHandler(onFail);
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(json(401, { error: { code: 'not_authenticated', message: 'Expired' } }))
      .mockResolvedValueOnce(json(401, { error: { code: 'not_authenticated', message: 'Invalid refresh token' } }));
    await expect(api.get('/orders')).rejects.toMatchObject({ status: 401 });
    expect(onFail).toHaveBeenCalledOnce();
    expect(getAccessToken()).toBeNull();
  });

  it('maps network failures to a friendly error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api.get('/orders')).rejects.toMatchObject({ code: 'network_error' });
  });
});

describe('validation helpers', () => {
  const err = {
    code: 'validation_error',
    message: 'Request validation failed',
    details: [{ loc: ['body', 'items', 0, 'quantity'], msg: 'must be positive' }],
  };

  it('maps field errors by full path and leaf name', () => {
    expect(fieldErrors(err)).toEqual({ 'items.0.quantity': 'must be positive', quantity: 'must be positive' });
    expect(fieldErrors({ code: 'conflict' })).toEqual({});
  });

  it('formats a readable message', () => {
    expect(errorMessage(err)).toBe('Request validation failed: items.0.quantity: must be positive');
    expect(errorMessage(null)).toBe('');
  });
});
