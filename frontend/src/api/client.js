/**
 * Centralized API client.
 *
 * - The access token lives in this module's memory only (never in Web Storage).
 * - On a 401 the client refreshes once via the httpOnly refresh cookie and
 *   retries the original request. Concurrent refreshes share one in-flight promise.
 * - Errors are normalized into ApiError using the backend envelope
 *   {"error": {"code", "message", "details"}}.
 */

export const API_BASE = '/api/v1';

let accessToken = null;
let refreshPromise = null;
let authFailureHandler = null;

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token) {
  accessToken = token || null;
}

/** Called when a refresh fails; the AuthContext uses it to send the user to /login. */
export function setAuthFailureHandler(fn) {
  authFailureHandler = fn;
}

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'error', details = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function parseError(res) {
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (body && body.error && typeof body.error === 'object') {
    const { code, message, details } = body.error;
    return new ApiError(message || `Request failed (${res.status})`, {
      status: res.status,
      code: code || 'error',
      details: details ?? null,
    });
  }
  if (body && body.detail) {
    const message = typeof body.detail === 'string' ? body.detail : 'Request validation failed';
    return new ApiError(message, {
      status: res.status,
      code: Array.isArray(body.detail) ? 'validation_error' : 'error',
      details: Array.isArray(body.detail) ? body.detail : null,
    });
  }
  return new ApiError(`Request failed (${res.status} ${res.statusText || ''})`.trim(), { status: res.status });
}

export function buildQuery(params) {
  if (!params) return '';
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '' || value === false && key !== 'active') return;
    if (Array.isArray(value)) {
      if (value.length) usp.set(key, value.join(','));
      return;
    }
    usp.set(key, String(value));
  });
  const qs = usp.toString();
  return qs ? `?${qs}` : '';
}

/** Exchange the refresh cookie for a new access token. De-duplicated. */
export function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      let res;
      try {
        res = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'include' });
      } catch {
        accessToken = null;
        throw new ApiError('Cannot reach the server. Check your connection.', { code: 'network_error' });
      }
      if (!res.ok) {
        accessToken = null;
        throw await parseError(res);
      }
      const data = await res.json();
      accessToken = data.access_token;
      return accessToken;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/**
 * Perform a request.
 * @param {string} path  path relative to /api/v1 (e.g. "/orders")
 * @param {object} opts  { method, query, body, formData, headers, raw, skipAuth, signal }
 */
export async function request(path, opts = {}) {
  const { method = 'GET', query, body, formData, headers = {}, raw = false, skipAuth = false, signal } = opts;
  const url = `${API_BASE}${path}${buildQuery(query)}`;

  const doFetch = async () => {
    const h = { Accept: 'application/json', ...headers };
    if (!skipAuth && accessToken) h.Authorization = `Bearer ${accessToken}`;
    let payload;
    if (formData) {
      payload = formData;
    } else if (body !== undefined) {
      h['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }
    try {
      return await fetch(url, { method, headers: h, body: payload, credentials: 'include', signal });
    } catch (e) {
      if (e && e.name === 'AbortError') throw e;
      throw new ApiError('Cannot reach the server. Check your connection.', { code: 'network_error' });
    }
  };

  let res = await doFetch();

  if (res.status === 401 && !skipAuth) {
    try {
      await refreshAccessToken();
    } catch (refreshErr) {
      if (authFailureHandler) authFailureHandler(refreshErr);
      throw await parseError(res);
    }
    res = await doFetch();
    if (res.status === 401 && authFailureHandler) {
      const err = await parseError(res);
      authFailureHandler(err);
      throw err;
    }
  }

  if (!res.ok) throw await parseError(res);
  if (raw) return res;
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const api = {
  get: (path, query, opts) => request(path, { ...opts, method: 'GET', query }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body }),
  patch: (path, body, opts) => request(path, { ...opts, method: 'PATCH', body }),
  put: (path, body, opts) => request(path, { ...opts, method: 'PUT', body }),
  del: (path, opts) => request(path, { ...opts, method: 'DELETE' }),
  upload: (path, formData, opts) => request(path, { ...opts, method: 'POST', formData }),
};

/**
 * Map FastAPI/Pydantic validation details ({loc, msg}) to a {field: message} object.
 * loc ["body","items",0,"quantity"] -> keys "items.0.quantity" and "quantity" (first one wins).
 */
export function fieldErrors(error) {
  const out = {};
  if (!error || error.code !== 'validation_error' || !Array.isArray(error.details)) return out;
  error.details.forEach((d) => {
    if (!d || !Array.isArray(d.loc)) return;
    const loc = d.loc[0] === 'body' || d.loc[0] === 'query' || d.loc[0] === 'path' ? d.loc.slice(1) : d.loc;
    const full = loc.join('.');
    if (full && !out[full]) out[full] = d.msg;
    const last = [...loc].reverse().find((p) => typeof p === 'string');
    if (last && !out[last]) out[last] = d.msg;
  });
  return out;
}

/** Human-readable error message, including validation details when not mapped to fields. */
export function errorMessage(error) {
  if (!error) return '';
  if (error.code === 'validation_error' && Array.isArray(error.details) && error.details.length) {
    const parts = error.details.map((d) => {
      const loc = Array.isArray(d.loc) ? d.loc.filter((p) => p !== 'body').join('.') : '';
      return loc ? `${loc}: ${d.msg}` : d.msg;
    });
    return `${error.message}: ${parts.join('; ')}`;
  }
  return error.message || String(error);
}
