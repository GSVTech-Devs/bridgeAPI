import type { Config } from "jest";
import nextJest from "next/jest.js";

const createJestConfig = nextJest({ dir: "./" });

const config: Config = {
  coverageProvider: "v8",
  testEnvironment: "<rootDir>/jest.environment.ts",
  setupFiles: ["<rootDir>/jest.polyfills.ts"],
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  // until-async is pure ESM — allow Jest to transform it
  transformIgnorePatterns: ["/node_modules/(?!(until-async)/)"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "^msw/node$":
      "<rootDir>/node_modules/msw/lib/node/index.js",
    "^@mswjs/interceptors$":
      "<rootDir>/node_modules/@mswjs/interceptors/lib/node/index.cjs",
    "^@mswjs/interceptors/ClientRequest$":
      "<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/ClientRequest/index.cjs",
    "^@mswjs/interceptors/XMLHttpRequest$":
      "<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/XMLHttpRequest/index.cjs",
    "^@mswjs/interceptors/fetch$":
      "<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/fetch/index.cjs",
    "^@mswjs/interceptors/WebSocket$":
      "<rootDir>/node_modules/@mswjs/interceptors/lib/browser/interceptors/WebSocket/index.cjs",
  },
};

export default createJestConfig(config);
