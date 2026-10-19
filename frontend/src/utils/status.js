/** Map every backend status/enum value to a badge tone. */
const TONES = {
  // neutral
  DRAFT: 'grey', PENDING: 'grey', PLANNED: 'grey', INACTIVE: 'grey', LOW: 'grey', RELEASED: 'grey', ARCHIVED: 'grey',
  // blue
  CONFIRMED: 'blue', READY_FOR_DISPATCH: 'blue', NORMAL: 'blue', MATERIAL: 'blue',
  // amber
  IN_PRODUCTION: 'amber', IN_PROGRESS: 'amber', ON_HOLD: 'amber', HIGH: 'amber', DISPATCHED: 'amber',
  // teal
  PARTIALLY_FULFILLED: 'teal', IN_TRANSIT: 'teal', PRODUCT: 'teal', ACTIVE: 'green',
  // green
  FULFILLED: 'green', COMPLETED: 'green', DELIVERED: 'green', PASS: 'green', APPROVED: 'green', DONE: 'green',
  CONSUMED: 'green',
  // red
  CANCELLED: 'red', REJECTED: 'red', FAILED: 'red', FAIL: 'red', URGENT: 'red', OVERDUE: 'red',
  // transaction types
  RECEIPT: 'green', ADJUSTMENT: 'amber', RESERVE: 'blue', RELEASE: 'grey', CONSUME: 'purple', PRODUCE: 'teal',
  DISPATCH: 'amber', RETURN: 'red',
};

export function statusTone(status) {
  if (!status) return 'grey';
  return TONES[String(status).toUpperCase()] || 'grey';
}

export const ORDER_STATUSES = ['DRAFT', 'CONFIRMED', 'IN_PRODUCTION', 'PARTIALLY_FULFILLED', 'FULFILLED', 'CANCELLED', 'REJECTED'];
export const DELIVERY_STATUSES = ['PENDING', 'READY_FOR_DISPATCH', 'DISPATCHED', 'IN_TRANSIT', 'DELIVERED', 'FAILED', 'CANCELLED'];
export const JOB_STATUSES = ['PLANNED', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CANCELLED'];
export const JOB_PRIORITIES = ['LOW', 'NORMAL', 'HIGH', 'URGENT'];
export const TXN_TYPES = ['RECEIPT', 'ADJUSTMENT', 'RESERVE', 'RELEASE', 'CONSUME', 'PRODUCE', 'DISPATCH', 'RETURN'];
export const ROLES = ['ADMIN', 'SALES', 'INVENTORY_MANAGER', 'PRODUCTION_MANAGER', 'QUALITY_INSPECTOR', 'DISPATCH', 'MANAGEMENT'];
export const DOC_TYPES = ['PROCEDURE', 'SPECIFICATION', 'POLICY', 'WORK_INSTRUCTION', 'QUALITY_STANDARD', 'CONTRACT', 'OTHER'];
export const DOC_STATUSES = ['DRAFT', 'APPROVED', 'ARCHIVED'];

/** Chart colours for order statuses (aligned with badge tones). */
export const STATUS_CHART_COLORS = {
  DRAFT: '#94a3b8', CONFIRMED: '#2563eb', IN_PRODUCTION: '#d97706', PARTIALLY_FULFILLED: '#0d9488',
  FULFILLED: '#16a34a', CANCELLED: '#dc2626', REJECTED: '#991b1b',
};

/** Statuses that may appear inside free-text audit summaries ("PENDING → READY_FOR_DISPATCH"). */
const SUMMARY_WORDS = new Set([...ORDER_STATUSES, ...DELIVERY_STATUSES, ...JOB_STATUSES, ...DOC_STATUSES, 'PASS', 'FAIL', 'ACTIVE', 'INACTIVE']);

/** Replace upper-case status codes in a sentence with readable words; identifiers like SO-1001 are untouched. */
export function friendlyText(text) {
  if (!text) return '';
  return String(text).replace(/\b[A-Z]+(?:_[A-Z]+)*\b/g, (w) => {
    if (!SUMMARY_WORDS.has(w)) return w;
    const s = w.replace(/_/g, ' ').toLowerCase();
    return s.charAt(0).toUpperCase() + s.slice(1);
  });
}

const ACTIVITY_ICONS = {
  auth: 'users', user: 'users', customer: 'customers', supplier: 'suppliers', order: 'orders', product: 'box',
  material: 'box', inventory: 'inventory', production: 'production', quality: 'quality', delivery: 'truck', document: 'documents',
};

/** Icon for an audit action such as "delivery.dispatched". */
export function activityIcon(action) {
  return ACTIVITY_ICONS[String(action || '').split('.')[0]] || 'clock';
}
