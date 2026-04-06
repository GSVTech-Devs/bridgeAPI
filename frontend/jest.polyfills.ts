// jest.polyfills.ts — runs in Node before jsdom sets up the environment.
// Restores the Node 18 Fetch API globals that jsdom would otherwise suppress.
// Required by MSW v2 (msw/node setupServer).
const { Response, Request, Headers, fetch } = globalThis as typeof globalThis & {
  fetch: typeof fetch;
};

if (typeof (global as Record<string, unknown>).Response === "undefined") {
  (global as Record<string, unknown>).Response = Response;
  (global as Record<string, unknown>).Request = Request;
  (global as Record<string, unknown>).Headers = Headers;
  (global as Record<string, unknown>).fetch = fetch;
}
