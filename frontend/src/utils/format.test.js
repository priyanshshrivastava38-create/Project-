import { describe, expect, it } from 'vitest';
import { formatMoney, formatNumber, formatQty, stripZeros, toNumber } from './format';
import { firstAllowedPath } from '../layouts/navConfig';

describe('format helpers', () => {
  it('handles backend decimal strings', () => {
    expect(toNumber('500.000')).toBe(500);
    expect(toNumber('abc')).toBeNull();
    expect(stripZeros('50.900')).toBe('50.9');
    expect(stripZeros('-0.000')).toBe('0');
    expect(formatNumber('1234.5000')).toBe('1,234.5');
    expect(formatQty('12.000', 'KG')).toBe('12 KG');
    expect(formatQty(null, 'KG')).toBe('—');
    expect(formatMoney('1999.5')).toBe('$1,999.50');
  });
});

describe('firstAllowedPath', () => {
  it('returns the first permitted nav entry or no-access', () => {
    expect(firstAllowedPath((p) => p === 'orders:read')).toBe('/orders');
    expect(firstAllowedPath(() => false)).toBe('/no-access');
  });
});

describe('friendlyText', () => {
  it('humanizes status codes but leaves identifiers alone', async () => {
    const { friendlyText, activityIcon } = await import('./status');
    expect(friendlyText('DEL-9003: PENDING → READY_FOR_DISPATCH (SO-1001)')).toBe('DEL-9003: Pending → Ready for dispatch (SO-1001)');
    expect(friendlyText('Steel spec EN 10025')).toBe('Steel spec EN 10025');
    expect(activityIcon('delivery.dispatched')).toBe('truck');
    expect(activityIcon('mystery')).toBe('clock');
  });
});
