import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});

if (!globalThis.crypto?.randomUUID) {
  globalThis.crypto = { ...(globalThis.crypto || {}), randomUUID: () => Math.random().toString(36).slice(2) };
}

// Recharts' ResponsiveContainer relies on ResizeObserver, which jsdom lacks.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
