import "@testing-library/jest-dom/vitest";

// React Flow (used by the evidence-graph panel) needs ResizeObserver, which
// jsdom does not implement.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

// jsdom's requestAnimationFrame is never driven by a real repaint clock, so
// rAF-based animations (e.g. AnimatedNumber's count-up) never settle in
// tests. Fire callbacks on a fast real timer instead — deterministic and
// quick, without weakening what the tests assert on the animation's end
// state. Unconditional: jsdom's own (non-firing) implementation must not win.
globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) =>
  setTimeout(() => cb(performance.now()), 4) as unknown as number) as typeof requestAnimationFrame;
globalThis.cancelAnimationFrame = ((id: number) => clearTimeout(id)) as typeof cancelAnimationFrame;
