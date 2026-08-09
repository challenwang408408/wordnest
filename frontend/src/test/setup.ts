import "@testing-library/jest-dom/vitest";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

Object.defineProperty(window, "speechSynthesis", {
  writable: true,
  value: {
    getVoices: () => [],
    speak: () => undefined,
    cancel: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  },
});

Object.defineProperty(window, "scrollTo", {
  writable: true,
  value: () => undefined,
});
