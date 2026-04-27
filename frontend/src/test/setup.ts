import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom lacks ResizeObserver and has zero layout — Recharts ResponsiveContainer
// won't render children without either. Fire the observer callback with a
// fixed size so charts render in tests.
class ResizeObserverStub {
  private cb: ResizeObserverCallback;
  constructor(cb: ResizeObserverCallback) {
    this.cb = cb;
  }
  observe(target: Element) {
    const entry = {
      target,
      contentRect: {
        width: 500,
        height: 300,
        top: 0,
        left: 0,
        bottom: 300,
        right: 500,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      } as DOMRectReadOnly,
      borderBoxSize: [],
      contentBoxSize: [],
      devicePixelContentBoxSize: [],
    } as unknown as ResizeObserverEntry;
    this.cb([entry], this as unknown as ResizeObserver);
  }
  unobserve() {}
  disconnect() {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}
if (typeof HTMLElement !== 'undefined') {
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
    configurable: true,
    get() {
      return 500;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
    configurable: true,
    get() {
      return 300;
    },
  });
}

afterEach(() => {
  cleanup();
});
