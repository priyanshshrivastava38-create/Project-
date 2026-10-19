/** Formatting helpers. Backend decimals arrive as strings such as "500.000". */

export function toNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : Number(String(value).trim());
  return Number.isFinite(n) ? n : null;
}

/** Strip trailing zeros: "500.000" -> "500", "50.900" -> "50.9", "0" -> "0". */
export function stripZeros(value) {
  if (value === null || value === undefined || value === '') return '';
  const s = String(value).trim();
  if (!/^-?\d+(\.\d+)?$/.test(s)) return s;
  if (!s.includes('.')) return s.replace(/^(-?)0+(?=\d)/, '$1');
  const out = s.replace(/0+$/, '').replace(/\.$/, '');
  return out === '-0' ? '0' : out;
}

/** Quantity / number with thousands separators and trailing zeros removed. */
export function formatNumber(value, { maxDecimals = 3, fallback = '—' } = {}) {
  const n = toNumber(value);
  if (n === null) return fallback;
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: maxDecimals }).format(n);
}

export function formatQty(value, uom) {
  const s = formatNumber(value);
  return uom && s !== '—' ? `${s} ${uom}` : s;
}

export function formatMoney(value, currency = 'USD', { fallback = '—' } = {}) {
  const n = toNumber(value);
  if (n === null) return fallback;
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`;
  }
}

export function formatPercent(value, { decimals = 1, fallback = '—' } = {}) {
  const n = toNumber(value);
  if (n === null) return fallback;
  return `${n.toFixed(decimals).replace(/\.0+$/, '')}%`;
}

function parseDate(value) {
  if (!value) return null;
  // Date-only strings ("2026-10-19") are calendar dates; avoid timezone shifts.
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split('-').map(Number);
    return new Date(y, m - 1, d);
  }
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(value, fallback = '—') {
  const d = parseDate(value);
  if (!d) return fallback;
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function formatDateTime(value, fallback = '—') {
  const d = parseDate(value);
  if (!d) return fallback;
  return d.toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function formatBytes(bytes) {
  const n = toNumber(bytes);
  if (n === null) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** Local YYYY-MM-DD for <input type="date">. */
export function isoDate(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/** "IN_PRODUCTION" -> "In production" */
export function humanize(value) {
  if (!value) return '';
  const s = String(value).replace(/[_\-.]+/g, ' ').toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}
