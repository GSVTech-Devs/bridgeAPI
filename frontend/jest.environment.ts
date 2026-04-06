// Custom Jest environment: extends jsdom with all Node 18 Web API globals.
// MSW v2 (msw/node) relies on these at module load time and they are absent
// from the jsdom sandbox even though Node 18 provides them.
import JSDOMEnvironment from "jest-environment-jsdom";

// Globals Node 18 exposes but jsdom does not inherit
const NODE18_WEB_GLOBALS = [
  "fetch",
  "Request",
  "Response",
  "Headers",
  "ReadableStream",
  "WritableStream",
  "TransformStream",
  "CompressionStream",
  "DecompressionStream",
  "TextEncoderStream",
  "TextDecoderStream",
  "ByteLengthQueuingStrategy",
  "CountQueuingStrategy",
  "ReadableStreamDefaultReader",
  "WritableStreamDefaultWriter",
  "BroadcastChannel",
  "FormData",
  "Blob",
] as const;

export default class FetchJSDOMEnvironment extends JSDOMEnvironment {
  async setup() {
    await super.setup();

    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { TextEncoder, TextDecoder } = require("util");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const g = global as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const env = this.global as any;

    if (typeof env.TextEncoder === "undefined") {
      env.TextEncoder = TextEncoder;
      env.TextDecoder = TextDecoder;
    }

    for (const name of NODE18_WEB_GLOBALS) {
      if (typeof env[name] === "undefined" && typeof g[name] !== "undefined") {
        env[name] = g[name];
      }
    }
  }
}
